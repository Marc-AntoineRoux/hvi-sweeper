import sys
import numpy as np
import time
import matplotlib.pyplot as plt
import struct
sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1
try:
    import keysight_tse as kthvi
except ImportError:
    import keysight_hvi as kthvi
from scipy.stats import binned_statistic_2d
import logging
import os
from firmware_manager import FirmwareVersionTracker
from generic_logging import quick_config
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

#%% 3rd Level: Classes and Functions to Use SD1/M3xxxA Instruments
#################################################################

class ModuleDescriptor:
    "Descriptor for module objects"
    def __init__(self, model_number, chassis_number, slot_number, options, card_num_VG = 0):
        if card_num_VG < 0 or card_num_VG > 3: raise ValueError("VG card number must be between 0 and 3.")
            
        self.model_number = str(model_number)
        self.chassis_number = int(chassis_number)
        self.slot_number = int(slot_number)
        self.options = str(options)
        self.card_num_VG = int(card_num_VG)

        if model_number in ("M3100A"): # M3102A not tested
            self.engine_name = "Digitizer Engine {}".format(slot_number)
        elif model_number in ("M3201A", "M3202A"):
            self.engine_name = "AWG Engine {}".format(slot_number)
        else:
            raise ValueError("{} module is not supported by the HVI application.".format(model_number))

    def __str__(self):
        return "Model: {}, Chassis: {}, Slot: {}, Options: {}, Engine name: {}, VG card number: {}".format(self.model_number, self.chassis_number, self.slot_number, self.options, self.engine_name, self.card_num_VG)

    @classmethod
    def from_dict(cls, data_dict):
        return cls(**data_dict) # dict keys and values must exactly match the __init__ arguments

class Module(ModuleDescriptor):
    "Class defining a modular instrument object and its properties"
    def __init__(self, config, instrument_object, num_channels, module_descriptor):
        self.instrument = instrument_object
        self.num_channels = num_channels

        if module_descriptor.model_number == "M3100A":
            if config.use_QD_emulator == True:
                self.firmware_to_load = config.QD_emulator_firmware
            else:
                self.firmware_to_load = config.M3100A_default_firmware
        
        elif module_descriptor.model_number == "M3202A":
            if config.use_virtual_gates == True:
                if config.nb_VG_awg_modules == 1:
                    if module_descriptor.card_num_VG == 1:
                        self.firmware_to_load  = config.M3202A_virtual_gates_firmware
                    else:
                        self.firmware_to_load = config.M3202A_voltage_registers_firmware
                elif config.nb_VG_awg_modules == 2:
                    self.firmware_to_load  = config.M3202A_VG_CC8_firmware_list[module_descriptor.card_num_VG]
                elif config.nb_VG_awg_modules == 3:
                    self.firmware_to_load  = config.M3202A_VG_CC12_firmware_list[module_descriptor.card_num_VG]
                else:
                    raise ValueError("{} VG AWG modules is not supported.".format(config.nb_VG_awg_modules))
            else:
                self.firmware_to_load = config.M3202A_voltage_registers_firmware

        elif module_descriptor.model_number == "M3201A":
            if config.use_virtual_gates == True:
                if config.nb_VG_awg_modules == 1:
                    if module_descriptor.card_num_VG == 1:
                        self.firmware_to_load  = config.M3201A_virtual_gates_firmware
                    else:
                        self.firmware_to_load = config.M3201A_voltage_registers_firmware
                elif config.nb_VG_awg_modules == 2:
                    self.firmware_to_load  = config.M3201A_VG_CC8_firmware_list[module_descriptor.card_num_VG]
                else:
                    raise ValueError("{} VG AWG modules is not supported with M3201A modules.".format(config.nb_VG_awg_modules))
            else:
                self.firmware_to_load = config.M3201A_voltage_registers_firmware
        else:
            raise ValueError("{} module is not supported by the HVI application.".format(module_descriptor.model_number))

        super().__init__(module_descriptor.model_number, module_descriptor.chassis_number, module_descriptor.slot_number, module_descriptor.options, module_descriptor.card_num_VG)

    def __str__(self):
        return "Model: {}, Chassis: {}, Slot: {}, Channel number: {}, Options: {}, Engine name: {}, Firmware to load: {}".format(self.model_number, self.chassis_number, self.slot_number, self.num_channels, self.options, self.engine_name, self.firmware_to_load.name)


def open_modules(config):
    """
    Opens and creates all the necessary instrument objects.
    Returns a dictionary of module objects whose keys are the HVI engine names.
    Please check SD1 3.x User Guide for options to open the instrument objects
    """
    # Checks flags defining if the code executes on HW/Simulation, SD1
    if config.hardware_simulated:
        logger.info("Code running in Simulation Mode")

    logger.info("Opening modules")
    # Initialize output variables
    num_modules = 0
    module_dict = {} # dictionary of modules

    # Open SD1 instrument objects
    for descriptor in config.module_descriptors:
        if descriptor.model_number in ("M3100A"): # M3102A not tested
            instr_obj = keysightSD1.SD_AIN()
        elif descriptor.model_number in ("M3201A", "M3202A"):
            instr_obj = keysightSD1.SD_AOU()
        else:
            raise ValueError("{} module is not supported by the HVI application.".format(descriptor.model_number))
        
        instr_obj_options = descriptor.options + ',simulate=true' if config.hardware_simulated else descriptor.options
        id = instr_obj.openWithOptions(descriptor.model_number, descriptor.chassis_number, descriptor.slot_number, instr_obj_options)
        logger.debug("{} module opened in slot {}, chassis {}".format(descriptor.model_number, descriptor.slot_number, descriptor.chassis_number))
        if id < 0:
            raise AttributeError("Error opening instrument in chassis: {}, slot: {}! Error code: {} - {}. Make sure the model, slot number and chassis number are correct.".format(descriptor.chassis_number, descriptor.slot_number, id, keysightSD1.SD_Error.getErrorMessage(id)))
        nCh = instr_obj.getOptions("channels")
        if nCh == "CH2":
            num_channels = 2
        elif nCh == "CH4":
            num_channels = 4
        elif nCh == "CH8": # bug fix for M3100A in simulation mode
            if config.hardware_simulated:
                num_channels = 4
            else:
                num_channels = 8
        else:
            raise ValueError("PXI module in chassis {}, slot {} returned number of channels = {} which is incorrect. Exiting... ".format(instr_obj.getChassis(), instr_obj.getSlot(), nCh))
        module_dict[descriptor.engine_name] = Module(config, instr_obj, num_channels, descriptor)
        num_modules += 1
        
    logger.info("Modules opened successfully")
    return module_dict

def configure_awg(config, awg_module:Module, num_channels = 4):
    config.logger.info("Configuring AWG {}".format(awg_module.slot_number))
    for channel in range(1, num_channels+1):
        # AWG queue flush
        awg_module.instrument.AWGstop(channel)
        awg_module.instrument.AWGflush(channel)
        # Set AWG mode
        awg_module.instrument.channelWaveShape(channel, config.awg_mode)
        awg_module.instrument.channelAmplitude(channel, config.amplitude)

def send_waveforms(config, awg_module: Module):
    # Load waveform to AWG memory
    awg_module.instrument.waveformFlush() #memory flush
    wave = keysightSD1.SD_Wave()

    for wfmNum, channel in enumerate([config.sin_channel, config.cos_channel]):
        if wfmNum == 0:
            _, waveformData = generateWaveformSine(ampl = 1, freq = config.freq_pnf, AWG_model = awg_module.model_number, nCycles = config.wfm_cycles)
        else:
            _, waveformData = generateWaveformCosine(ampl = 1, freq = config.freq_pnf, AWG_model = awg_module.model_number, nCycles = config.wfm_cycles)

        wave.newFromArrayDouble(keysightSD1.SD_WaveformTypes.WAVE_ANALOG, waveformData)
        error = wave.getStatus()
        if error < 0:  raise ValueError("Waveform creation error: {}, {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
        availableRAM = awg_module.instrument.waveformLoad(wave, wfmNum, wave.PADDING_ZERO)
        # print(availableRAM, "memory remaining on AWG") # seems to be printing used memory instead of remaining?

        # AWG configuration
        awg_module.instrument.AWGqueueConfig(channel, config.queue_mode)
        awg_module.instrument.AWGqueueSyncMode(channel, config.sync_mode)
        # Queue waveform to the selected channel
        awg_module.instrument.AWGqueueWaveform(channel, wfmNum, config.awg_trigger_mode, config.start_delay, config.num_cycles, config.awg_prescaler)
        awg_module.instrument.channelAmplitude(channel, 1)
        awg_module.instrument.AWGstart(channel) # AWG starts and waits for an AWG trigger


def configure_digitizer(config, digitizer_module: Module, num_channels = 4, num_cycles_override = None):
    config.logger.info("Configuring Digitizer {}".format(digitizer_module.slot_number))
    # Input settings
    prescaler = config.dig_prescaler
    fullscale = config.fullscale
    num_cycles = config.num_cycles
    points_per_cycle = config.acquisition_points_per_cycle
    acquisition_delay = config.acquisition_delay
    trigger_mode = config.dig_trigger_mode

    if num_cycles_override is not None:
        num_cycles = num_cycles_override

    # TODO: reset QD emulator to make long measurements, to be tested
    # if config.use_QD_emulator:
        # Reset FPGA to avoid timeout
        # config.logger.debug("Resetting digitizer FPGA")
        # reset_mode = keysightSD1.SD_ResetMode.PULSE
        # digitizer_module.instrument.FPGAreset(reset_mode)
        # load_digitizer(config, digitizer_module)

    # Configure DAQ channels
    for n_DAQ in range (1, num_channels+1):
        # DAQstop: stops any previous acquisition
        digitizer_module.instrument.DAQstop(n_DAQ)
        
        # Resets the DAQ
        digitizer_module.instrument.DAQflush(n_DAQ)

        if config.load_digitizer_channel_config == True: # changing the impedance or coupling can create voltage spikes
            # Digitizer channel configuration
            digitizer_module.instrument.channelInputConfig(n_DAQ, fullscale, keysightSD1.AIN_Impedance.AIN_IMPEDANCE_HZ, keysightSD1.AIN_Coupling.AIN_COUPLING_DC)
        
        digitizer_module.instrument.channelPrescalerConfig(n_DAQ, prescaler)

        # DAQ acquisitions configuration
        digitizer_module.instrument.DAQconfig(n_DAQ, points_per_cycle, num_cycles, acquisition_delay, trigger_mode)
    
        # DAQstart: digitizer channels get started and are waiting for the DAQ trigger commands that trigger the acquisition of each cycle of data points
        digitizer_module.instrument.DAQstart(n_DAQ)

    return points_per_cycle



#%% 2nd Level: Functions to Define, Program, Execute HVI
########################################################

def define_hvi_resources(sys_def, module_dict, config):
    """
    Configures all the necessary resources for the HVI application to execute: HW platform, engines, actions, triggers, etc.
    """
    # Define HW platform: chassis, interconnections, PXI trigger resources, synchronization, HVI clocks
    config.logger.info("Defining HW platform")
    define_hw_platform(sys_def, config)

    # Define all the HVI engines to be included in the HVI
    config.logger.info("Defining HVI engines")
    define_hvi_engines(sys_def, module_dict)

    # Define FPGA actions, events and other configurations
    config.logger.info("Defining FPGA resources")
    define_fpga_resources(sys_def, module_dict, config)

    # Define list of actions to be executed
    config.logger.info("Defining HVI actions")
    define_hvi_actions(sys_def, module_dict, config)

def define_hw_platform(sys_def, config):
    """
    Define HW platform: chassis, interconnections, PXI trigger resources, synchronization, HVI clocks
    """
    # Add chassis resources
    # For multi-chassis setup details see programming example documentation
    for chassis_number in config.chassis_list:
        if config.hardware_simulated:
            sys_def.chassis.add_with_options(chassis_number, 'Simulate=True,DriverSetup=model=M9018B,NoDriver=True') # M9018B in example, M9019A is our model
        else:
            sys_def.chassis.add(chassis_number)

    # Add M9031 modules for multi-chassis setups
    if config.M9031_descriptors:
        interconnects = sys_def.interconnects
        for descriptor in config.M9031_descriptors:
            interconnects.add_M9031_modules(descriptor.chassis_1, descriptor.slot_1, descriptor.chassis_2, descriptor.slot_2)

    # Assign the defined PXI trigger resources
    sys_def.sync_resources = config.pxi_sync_trigger_resources

    # Assign clock frequencies that are outside the set of the clock frequencies of each HVI engine
    # Use the code line below if you want the application to be in sync with the 10 MHz clock
    sys_def.non_hvi_core_clocks = [10e6]


def define_hvi_engines(sys_def, module_dict):
    """
    Define all the HVI engines to be included in the HVI
    """
    # For each instrument to be used in the HVI application add its HVI Engine to the HVI Engine Collection
    for engine_name, module in zip(module_dict.keys(), module_dict.values()):
        sys_def.engines.add(module.instrument.hvi.engines.main_engine, engine_name)

def define_hvi_actions(sys_def, module_dict, config):
    """
    This function defines a list of DAQ/AWG trigger actions for each module,
    to be executed by the "action-execute" instructions within the HVI sequence.
    The number of actions in each engine's list depends on the intrument's number of channels.
    """
    # For each engine, add each HVI Actions to be executed to its own HVI Action Collection
    for engine_name, module in zip(module_dict.keys(), module_dict.values()):
        for ch_index in range(1, module.num_channels + 1):
            # Actions need to be added to the engine's action list so that they can be executed
            # Example: hvi.engines[i].actions.add(module_dict[i].hvi.actions.awg1_trigger, 'AWG1_trigger')
            if module.model_number in ["M3100A", "M3102A"]:
                action_name = config.daq_trigger_name+ str(ch_index) # arbitrary user-defined name
                instrument_action = "daq{}_trigger".format(ch_index) # name decided by instrument API
            elif module.model_number in ["M3201A", "M3202A"]:
                action_name = config.awg_trigger_name+ str(ch_index) # arbitrary user-defined name
                instrument_action = "awg{}_trigger".format(ch_index) # name decided by instrument API
            else:
                raise ValueError("Module model number {} is not supported by the HVI application. Exiting...".format(module.model_number))
            action_id = getattr(module.instrument.hvi.actions, instrument_action)
            sys_def.engines[engine_name].actions.add(action_id, action_name)

def define_hvi_actions_fly(sys_def, fly_awg_module:Module, config):
    """
    This function defines the AWG trigger actions for the "fly" waveforms,
    to be executed by the "action-execute" instructions within the HVI sequence.
    """

    action_name = config.awg_trigger_name+ str(config.sin_channel) # arbitrary user-defined name
    instrument_action = "awg{}_trigger".format(config.sin_channel) # name decided by instrument API
    action_id = getattr(fly_awg_module.instrument.hvi.actions, instrument_action)
    sys_def.engines[config.fly_awg_engine_name].actions.add(action_id, action_name)

    action_name = config.awg_trigger_name+ str(config.cos_channel) # arbitrary user-defined name
    instrument_action = "awg{}_trigger".format(config.cos_channel) # name decided by instrument API
    action_id = getattr(fly_awg_module.instrument.hvi.actions, instrument_action)
    sys_def.engines[config.fly_awg_engine_name].actions.add(action_id, action_name)


def define_fpga_resources(sys_def, module_dict, config):
    """
    Define FPGA actions, events and other configurations
    """
    if config.hardware_simulated == False:
        for engine_name, module in zip(module_dict.keys(), module_dict.values()):
            # Get engine sandbox
            sandbox = sys_def.engines[engine_name].fpga_sandboxes[config.M3xxxA_sandbox]
            # Load to the sandboxes .k7z project created using Pathwave FPGA
            # This operation is necessary for HVI to list all the FPGA blocks contrined in the designed FPGA FW
            if module.model_number == "M3202A" or module.model_number == "M3201A":
                sandbox.load_from_k7z(module.firmware_to_load.path)
            elif module.model_number == "M3100A":
                sandbox.load_from_k7z(module.firmware_to_load.path) # use only for HVI communucation (MainEngine_Memory)
            else:
                raise ValueError("Module model number {} is not supported by the HVI application. Exiting...".format(module.model_number))

def program_step_to_target_voltage(sequencer, awg_module: Module, awg_sequence, config, AWG_channel, voltage_channel, target_voltage_register, slew_rate, use_dV_from_config = False, output_voltage=True, source_VG_module=None):
    """
    Program a step in the AWG sequence to reach the target voltage.

    Parameters
    ----------
    sequencer : kthvi.Sequencer
        HVI sequencer object.
    awg_module : Module
        AWG module object.
    awg_sequence : HVI sequence
        HVI sequence of the AWG module.
    config : ApplicationConfig1D
        Configuration of the HVI program.
    AWG_channel : int
        Number of the AWG channel to output the voltage.
    voltage_channel : HVI register
        Register of the voltage channel to sweep.
    target_voltage_register : HVI register
        Register of the target voltage to reach.
    slew_rate : float
        Slew rate of the voltage ramp.
    use_dV_from_config : bool, optional
        Use the voltage increment set in the config or not, by default False. If False, the voltage increment is set to 1 by default.
    output_voltage : bool, optional
        Choose if the sequence outputs the voltage to the AWG channel, by default True. Otherwise, the voltage value is written to the virtual gates memory bank in the FPGA firmware.
    source_VG_module : Module, optional
        Source module of the voltage to be sent to other virtual gate modules, by default None.

    Returns
    -------
    None
    """
    max_positive = 32767 # max integer considered as positive (1.5V = 32767, -1.5V = 32768 or 32769)
    max_negative = 65536

    awg_engine_name = awg_module.engine_name

    # Get register values
    awg_registers = sequencer.sync_sequence.scopes[awg_engine_name].registers
    sweep_direction = awg_registers[config.sweep_direction_name]
    neg_counter = awg_registers[config.neg_counter_name]
    # slew_time = awg_registers[config.slew_time_name]
    # awg_debug = awg_registers[config.awg_debug_name]
    if use_dV_from_config:
        voltage_increment = awg_registers[config.voltage_increment_name]
        neg_voltage_increment = awg_registers[config.neg_voltage_increment_name]

      ###########################################################################
    # Check if the target voltage is smaller or bigger than the actual voltage and define the sweep direction accordingly
    # Configure IF condition
    if_condition = kthvi.Condition.register_comparison(target_voltage_register, kthvi.ComparisonOperator.LESS_THAN, voltage_channel)

    # Add If statement
    enable_ifbranches_time_matching = True # Set flag that enables to match the execution time of all the IF branches
    instruction_label = config.instruction_name.unique("Target voltage < V Chx")
    if_statement = awg_sequence.add_if(instruction_label, 430, if_condition, enable_ifbranches_time_matching)

    # Program IF branch
    if_sequence = if_statement.if_branch.sequence
    # Add statements in if-sequence
    instruction_label = config.instruction_name.unique("Sweep dir = -dV")
    instruction = if_sequence.add_instruction(instruction_label, 10+50, if_sequence.instruction_set.assign.id)
    instruction.set_parameter(if_sequence.instruction_set.assign.destination.id, sweep_direction)
    if use_dV_from_config:
        instruction.set_parameter(if_sequence.instruction_set.assign.source.id, neg_voltage_increment)
    else:
        instruction.set_parameter(if_sequence.instruction_set.assign.source.id, -1) 

    # Else-branch
    # Program Else branch
    else_sequence = if_statement.else_branch.sequence
    # Add statements in Else-sequence
    instruction_label = config.instruction_name.unique("Sweep dir = dV")
    instruction = else_sequence.add_instruction(instruction_label, 10+50, else_sequence.instruction_set.assign.id)
    instruction.set_parameter(else_sequence.instruction_set.assign.destination.id, sweep_direction)
    if use_dV_from_config:
        instruction.set_parameter(else_sequence.instruction_set.assign.source.id, voltage_increment)
    else:
        instruction.set_parameter(else_sequence.instruction_set.assign.source.id, 1)

    ###########################################################################
    # Check if the target voltage is negative
    instruction_label = config.instruction_name.unique("Negative counter = 0")
    instruction = awg_sequence.add_instruction(instruction_label, 10+50, awg_sequence.instruction_set.assign.id)
    instruction.set_parameter(awg_sequence.instruction_set.assign.destination.id, neg_counter)
    instruction.set_parameter(awg_sequence.instruction_set.assign.source.id, 0)

    # Configure IF condition
    if_condition = kthvi.Condition.register_comparison(target_voltage_register, kthvi.ComparisonOperator.GREATER_THAN, max_positive) # if target_voltage_register is negative

    # Add If statement
    enable_ifbranches_time_matching = True # Set flag that enables to match the execution time of all the IF branches
    instruction_label = config.instruction_name.unique("Target voltage > max positive")
    if_statement = awg_sequence.add_if(instruction_label, 100, if_condition, enable_ifbranches_time_matching)

    # Program IF branch
    if_sequence = if_statement.if_branch.sequence
    # Add statements in if-sequence
    instruction_label = config.instruction_name.unique("Negative counter +1")
    instruction = if_sequence.add_instruction(instruction_label, 10+80, if_sequence.instruction_set.add.id)
    instruction.set_parameter(if_sequence.instruction_set.add.destination.id, neg_counter)
    instruction.set_parameter(if_sequence.instruction_set.add.left_operand.id, neg_counter)
    instruction.set_parameter(if_sequence.instruction_set.add.right_operand.id, 1)

    ###########################################################################
    # Check if the current voltage is negative
    # Configure IF condition
    if_condition = kthvi.Condition.register_comparison(voltage_channel, kthvi.ComparisonOperator.GREATER_THAN, max_positive) # if V Ch1 is negative

    # Add If statement
    enable_ifbranches_time_matching = True # Set flag that enables to match the execution time of all the IF branches
    instruction_label = config.instruction_name.unique("V Chx > max positive")
    if_statement = awg_sequence.add_if(instruction_label, 100, if_condition, enable_ifbranches_time_matching)

    # Program IF branch
    if_sequence = if_statement.if_branch.sequence
    # Add statements in if-sequence
    instruction_label = config.instruction_name.unique("Negative counter +1")
    instruction = if_sequence.add_instruction(instruction_label, 10+80, if_sequence.instruction_set.add.id)
    instruction.set_parameter(if_sequence.instruction_set.add.destination.id, neg_counter)
    instruction.set_parameter(if_sequence.instruction_set.add.left_operand.id, neg_counter)
    instruction.set_parameter(if_sequence.instruction_set.add.right_operand.id, 1)

    ###########################################################################
    # If only one voltage value is negative (bigger than 32 767), the negative voltage integer value will be bigger than the positive (less than 32 767) voltage value.
    # The IF condition will be inverted so it needs to be corrected by inverting it.
    # Configure IF condition
    if_condition = kthvi.Condition.register_comparison(neg_counter, kthvi.ComparisonOperator.EQUAL_TO, 1)

    # Add If statement
    enable_ifbranches_time_matching = True # Set flag that enables to match the execution time of all the IF branches
    instruction_label = config.instruction_name.unique("Neg counter = 1")
    if_statement = awg_sequence.add_if(instruction_label, 100, if_condition, enable_ifbranches_time_matching)

    # Program IF branch
    if_sequence = if_statement.if_branch.sequence
    # Add statements in if-sequence
    instruction_label = config.instruction_name.unique("V Chx -= sweep direction")
    instruction = if_sequence.add_instruction(instruction_label, 10+80, if_sequence.instruction_set.subtract.id)
    instruction.set_parameter(if_sequence.instruction_set.add.destination.id, voltage_channel)
    instruction.set_parameter(if_sequence.instruction_set.add.left_operand.id, voltage_channel)
    instruction.set_parameter(if_sequence.instruction_set.add.right_operand.id, sweep_direction)

    # Else-branch
    # Program Else branch
    else_sequence = if_statement.else_branch.sequence
    # Add statements in Else-sequence
    instruction_label = config.instruction_name.unique("V Chx += sweep direction")
    instruction = else_sequence.add_instruction(instruction_label, 10+80, else_sequence.instruction_set.add.id)
    instruction.set_parameter(else_sequence.instruction_set.add.destination.id, voltage_channel)
    instruction.set_parameter(else_sequence.instruction_set.add.left_operand.id, voltage_channel)
    instruction.set_parameter(else_sequence.instruction_set.add.right_operand.id, sweep_direction)

    ###########################################################################
    # Keep the voltage value within 16 bits
    # Configure IF condition
    if_condition = kthvi.Condition.register_comparison(voltage_channel, kthvi.ComparisonOperator.EQUAL_TO, max_negative+1)

    # Add If statement
    enable_ifbranches_time_matching = True # Set flag that enables to match the execution time of all the IF branches
    instruction_label = config.instruction_name.unique("V Chx = max negative + 1")
    if_statement = awg_sequence.add_if(instruction_label, 100, if_condition, enable_ifbranches_time_matching)

    # Program IF branch
    if_sequence = if_statement.if_branch.sequence
    # Add statements in if-sequence
    instruction_label = config.instruction_name.unique("V Chx = 0")
    instruction = if_sequence.add_instruction(instruction_label, 10+80, if_sequence.instruction_set.assign.id)
    instruction.set_parameter(if_sequence.instruction_set.assign.destination.id, voltage_channel)
    instruction.set_parameter(if_sequence.instruction_set.assign.source.id, 0)

    ###########################################################################

    if output_voltage:
        instruction_label = config.instruction_name.unique("set AWG offset")
        instruction = awg_sequence.add_instruction(instruction_label, 200, awg_module.instrument.hvi.instruction_set.set_offset.id)
        instruction.set_parameter(awg_module.instrument.hvi.instruction_set.set_offset.channel.id, AWG_channel)
        instruction.set_parameter(awg_module.instrument.hvi.instruction_set.set_offset.value.id, voltage_channel)
    else:
        if config.nb_VG_awg_modules > 1:
            instruction_label = config.instruction_name.unique("Write voltage register to register bank")
            writeFpgaReg = awg_sequence.add_instruction(instruction_label, 100, awg_sequence.instruction_set.fpga_register_write.id)
            voltage_register_VG = awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers["Voltage_card{}_V_ch{}".format(source_VG_module.card_num_VG, (source_VG_module.card_num_VG-1)*4+AWG_channel)] # card1 has channels 1-4, card2 has channels 5-8
            writeFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_write.fpga_register.id, voltage_register_VG)
            writeFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_write.value.id, voltage_channel)

    ###########################################################################
    # Instructions for debugging
    #
    # Read FPGA Register
    # instruction_label = config.instruction_name.unique("Read FPGA Register Bank Voltage_Chx test")
    # readFpgaReg = awg_sequence.add_instruction(instruction_label, 100, awg_sequence.instruction_set.fpga_register_read.id)
    # readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.destination.id, awg_debug)
    # fpga_voltage_channel_name = config.fpga_voltage_chx_name.format(AWG_channel)
    # fpga_voltage = awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers[fpga_voltage_channel_name]
    # readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.fpga_register.id, fpga_voltage)

    # if not config.hardware_simulated:
    #     # Read FPGA Register
    #     instruction_label = config.instruction_name.unique("Read FPGA Register Bank debug")
    #     readFpgaReg = awg_sequence.add_instruction(instruction_label, 100, awg_sequence.instruction_set.fpga_register_read.id)
    #     readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.destination.id, awg_debug)
    #     fpga_debug = awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers[config.fpga_debug_name]
    #     readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.fpga_register.id, fpga_debug)

    # instruction_label = config.instruction_name.unique("Loop Debug += 1")
    # instruction = awg_sequence.add_instruction(instruction_label, 200, awg_sequence.instruction_set.add.id)
    # instruction.set_parameter(awg_sequence.instruction_set.add.destination.id, awg_debug)
    # instruction.set_parameter(awg_sequence.instruction_set.add.left_operand.id, awg_debug)
    # instruction.set_parameter(awg_sequence.instruction_set.add.right_operand.id, 1)

    # if not config.hardware_simulated:
    #     # Write FPGA Register
    #     instruction_label = config.instruction_name.unique("Write FPGA Register Bank debug")
    #     writeFpgaReg = awg_sequence.add_instruction(instruction_label, 100, awg_sequence.instruction_set.fpga_register_write.id)
    #     fpga_debug = awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers[config.fpga_debug_name]
    #     writeFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_write.fpga_register.id, fpga_debug)
    #     writeFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_write.value.id, awg_debug)

    ###########################################################################

    # Wait Time
    instruction_label = config.instruction_name.unique("Wait")
    # awg_sequence.add_wait_time(instruction_label, 20, slew_time)

    if use_dV_from_config:
        delay =  calc_slewTimer(config.vi_1d_internal, config.vf_1d_internal, slew_rate, dV=config.dV)
    else:
        delay =  calc_slewTimer(config.vi_1d_internal, config.vf_1d_internal, slew_rate)

    awg_sequence.add_delay(instruction_label, round(delay*10))   


def digitizer_measurement_chx(dig_sequence, config):

    # Get register values
    digitizer_registers = dig_sequence.scope.registers
    stabilization_time = digitizer_registers[config.stabilization_time_name]
    integration_pause_time = digitizer_registers[config.integration_pause_time_name]
    loop_counter = digitizer_registers[config.loop_counter_1d_name]

    instruction_label = config.instruction_name.unique("Stabilization Time")
    dig_sequence.add_wait_time(instruction_label, 50, stabilization_time)
    # dig_sequence.add_delay(instruction_label, stabilization_time)

    action_list = dig_sequence.engine.actions
    instruction_label = config.instruction_name.unique("DaqTrigger")
    instruction = dig_sequence.add_instruction(instruction_label, 20, dig_sequence.instruction_set.action_execute.id)
    instruction.set_parameter(dig_sequence.instruction_set.action_execute.action.id, action_list)

    # Wait for integration time
    instruction_label = config.instruction_name.unique("Integration and Pause Time")
    dig_sequence.add_wait_time(instruction_label, 20, integration_pause_time)
    # dig_sequence.add_delay(instruction_label, integration_pause_time)

    # Reset loop counter to measure only at specific time intervals
    instruction_label = config.instruction_name.unique("Loop Counter = 0")
    instruction = dig_sequence.add_instruction(instruction_label, 10+50, dig_sequence.instruction_set.assign.id)
    instruction.set_parameter(dig_sequence.instruction_set.assign.destination.id, loop_counter)
    instruction.set_parameter(dig_sequence.instruction_set.assign.source.id, 0)


def export_hvi_sequences(sequencer, filename):
    """
    Exports the programmed HVI sequences to text format
    """
    # Generate HVI sequence description text
    logger.info("Generating HVI sequence description text...")
    output = sequencer.sync_sequence.to_string(kthvi.OutputFormat.DEBUG)

    # Write file
    logger.info("Exporting HVI sequence to file...")
    with open(filename, "w+") as text_file:
        # text_file.seek(0)
        text_file.write(output)
        text_file.close()

    logger.info("Programmed HVI sequences exported to file {}".format(filename))

def set_hvi_done(sequencer, dig_module: Module, config):
    """
    Set the HVI done register to 1.

    Parameters
    ----------
    sequencer : kthvi.Sequencer
        HVI sequencer object.
    dig_module : Module
        Digitizer module object.
    config : ApplicationConfig1D or ApplicationConfig2D
        Configuration of the HVI program.
    """
    instruction_label = config.instruction_name.unique("HVI Done")
    sync_block = sequencer.sync_sequence.add_sync_multi_sequence_block(instruction_label, 30)
    dig_sequence = sync_block.sequences[dig_module.engine_name]
    dig_registers = dig_sequence.scope.registers
    hvi_done = dig_registers[config.hvi_done_name] 
    instruction_label = config.instruction_name.unique("HVI Done = 1")
    instruction = dig_sequence.add_instruction(instruction_label, 10, dig_sequence.instruction_set.assign.id)
    instruction.set_parameter(dig_sequence.instruction_set.assign.destination.id, hvi_done)
    instruction.set_parameter(dig_sequence.instruction_set.assign.source.id, 1)
    
#%% Python functions
def calc_slewTimer(Vi, Vf, slewRate, dV=45.7778e-6):
    """
    Calculates the time to wait for each voltage step to achieve a given slew rate.

    Parameters
    ----------
    Vi : float
        Initial voltage.
    Vf : float
        Final voltage.
    slewRate : float
        Slew rate in V/s.
    dV : float
        Voltage step size in V.
    
    Returns
    -------
    int
        Time to wait in 10ns steps.
    """
    HVI_loop_time = 1090e-9 # fixed by the HVI code used (program_step_to_target_voltage 2023-06-25)
    if slewRate == 0:
        slewTimer = 1 # minimum time to wait for HVI compiler
    else:
        # slewTimer = int((dV/slewRate)*1e8) # not taking into account the HVI execution time
        slewTimer = int((dV/slewRate - HVI_loop_time)*1e8)*2 # x2 because AWG is outputting twice the voltage on high impedance loads
        if slewTimer <= 0:
            slewTimer = 1 # minimum time to wait for HVI compiler
            logger.info("Min slewTimer achieved. Slew rate: {:.03f} V/s".format(dV/(HVI_loop_time+slewTimer*10e-9)))

    return slewTimer

def calc_stepSize(Vi, Vf, nbSteps):
    """
    Calculates the step size between two voltage steps.
    
    Parameters
    ----------
    Vi : float
        Initial voltage.
    Vf : float  
        Final voltage.
    nbSteps : int
        Number of steps between Vi and Vf (including Vi and Vf, so 2 minimum).
        
    Returns
    -------
    float
        Step size between two voltage steps.
    """
    if nbSteps == 1:
        stepSize = 0
    else:
        stepSize = abs(Vf - Vi)/(nbSteps - 1)

    return stepSize

def calc_step_counter(Vi, Vf, nbSteps, dV=45.7778e-6):
    """ 
    Calculates the number of voltage increments needed to go through one step.

    Parameters
    ----------
    Vi : float
        Initial voltage.
    Vf : float
        Final voltage.
    nbSteps : int
        Number of steps between Vi and Vf (including Vi and Vf, so 2 minimum).
    dV : float, optional
        Approximately the smallest step size possible with the AWG (measured after one voltage step in HVI), by default 45.7778e-6.

    Returns
    -------
    int
        Number of steps needed to go from Vi to Vf with a step size of dV.
    """    
    stepSize = calc_stepSize(Vi, Vf, nbSteps)

    # in some cases there are to many steps and sometimes one step is missing. To investigate
    if stepSize == 0:
        return 0
    else:
        return int((stepSize/dV)) # or int((stepSize/dV)-1)?
    

def verify_sweep_parameters_1d(config, warning_string="", silence_warnings=False, auto_fix=False):
    """
    Verifies if the 1D sweep parameters are valid.
    Can be chained with other verification functions since it takes other warnings as an input and returns a string with the input warnings and potentially the new warnings.

    Parameters
    ----------
    config : ApplicationConfig1D
        Configuration of the HVI program.
    warning_string : str, optional
        String containing all the warnings returned by other verication functions, by default "".
    silence_warnings : bool, optional
        If True, no warning will be raised to allow the next verification function to be executed, by default False.
    auto_fix : bool, optional
        If True, the config will be updated with the new parameters and no warning will be raised, by default False.

    Returns
    -------
    str
        String containing all the warnings.

    Raises
    ------
    ValueError
        If the voltage step is too small for the 1D sweep. 
    ValueError
        If the voltage step between measurements is not a multiple of the voltage step between vi and vf.
    """
    config.logger.info("Verifying sweep parameters...")
    ramp_counter_1d = calc_step_counter(config.vi_1d_internal, config.vf_1d_internal, 2, dV=config.dV)
    step_counter_1d = calc_step_counter(config.vi_1d_internal, config.vf_1d_internal, config.num_steps_1d, dV=config.dV)

    if step_counter_1d < 1:
        new_num_steps_1d = int(abs(config.vf_1d_internal - config.vi_1d_internal)/config.dV)+1
        if auto_fix:
            config.num_steps_1d = new_num_steps_1d
            step_counter_1d = calc_step_counter(config.vi_1d_internal, config.vf_1d_internal, config.num_steps_1d, dV=config.dV)
            config.logger.info("Number of 1D steps updated to {}".format(new_num_steps_1d))
        else:
            warning = "Requested voltage step is too small for the 2D sweep. Maximum number of points is {} for a sweep between {} and {} V with a voltage increment of {}.".format(new_num_steps_1d, config.vi_1d_internal, config.vf_1d_internal, config.dV)
            warning_string = warning_string + warning + "\n"
            step_counter_1d = 1 # set the step counter to 1 to avoid division by 0 in the next if statement

    if step_counter_1d > ramp_counter_1d:
        raise ValueError("The voltage step between measurements ({}) cannot be bigger than the voltage between vi and vf ({}) for the 1D sweep.".format(step_counter_1d, ramp_counter_1d))

    if (ramp_counter_1d // step_counter_1d)+1 != config.num_steps_1d:
        new_num_steps_1d = (ramp_counter_1d // step_counter_1d)+1
        if auto_fix:
            config.num_steps_1d = new_num_steps_1d
            step_counter_1d = calc_step_counter(config.vi_1d_internal, config.vf_1d_internal, config.num_steps_1d, dV=config.dV)
            config.logger.info("Number of 1D steps updated to {}".format(new_num_steps_1d))
        else:
            warning = "The voltage step between measurements ({}) is not a multiple of the voltage step between vi and vf ({}) for the 1D sweep. The number of steps should be {}".format(step_counter_1d, ramp_counter_1d, new_num_steps_1d)
            warning_string = warning_string + warning + "\n"
    
    if not silence_warnings and warning_string != "": # if there are warnings
        raise ValueError(warning_string)

    config.logger.info("1D params verification complete")

    return warning_string

def verify_sweep_parameters_2d(config, warning_string="", silence_warnings=False, auto_fix=False):
    """
    Verifies if the 2D sweep parameters are valid.

    Parameters
    ----------
    config : ApplicationConfig2D
        Configuration of the HVI program.
    warning_string : str, optional
        String containing all the warnings returned by other verication functions, by default "".
    silence_warnings : bool, optional
        If True, no warning will be raised to allow the next verification function to be executed, by default False.
    auto_fix : bool, optional
        If True, the config will be updated with the new parameters and no warning will be raised, by default False.
    
    Returns
    -------
    str
        String containing all the warnings.
    
    Raises
    ------
    ValueError
        If the voltage step is too small for the 2D sweep.
    ValueError
        If the voltage step between measurements is not a multiple of the voltage step between vi and vf.
    """
    config.logger.info("Verifying sweep parameters...")
    ramp_counter_2d = calc_step_counter(config.vi_2d_internal, config.vf_2d, 2, dV=config.dV)
    step_counter_2d = calc_step_counter(config.vi_2d_internal, config.vf_2d, config.num_steps_2d, dV=config.dV)

    if step_counter_2d < 1:
        new_num_steps_2d = int(abs(config.vf_2d - config.vi_2d_internal)/config.dV)+1
        if auto_fix:
            config.num_steps_2d = new_num_steps_2d
            step_counter_2d = calc_step_counter(config.vi_2d_internal, config.vf_2d, config.num_steps_2d, dV=config.dV)
            config.logger.info("Number of 2D steps updated to {}".format(new_num_steps_2d))
        warning = "Requested voltage step is too small for the 2D sweep. Maximum number of points is {} for a sweep between {} and {} V with a voltage increment of {}.".format(new_num_steps_2d, config.vi_2d_internal, config.vf_2d, config.dV)
        warning_string = warning_string + warning + "\n"
        step_counter_2d = 1 # set the step counter to 1 to avoid division by 0 in the next if statement

    if step_counter_2d > ramp_counter_2d:
        raise ValueError("The voltage step between measurements ({}) cannot be bigger than the voltage between vi and vf ({}) for the 2D sweep.".format(step_counter_2d, ramp_counter_2d))

    if (ramp_counter_2d // step_counter_2d)+1 != config.num_steps_2d:
        new_num_steps_2d = (ramp_counter_2d // step_counter_2d)+1
        if auto_fix:
            config.num_steps_2d = new_num_steps_2d
            step_counter_2d = calc_step_counter(config.vi_2d_internal, config.vf_2d, config.num_steps_2d, dV=config.dV)
            config.logger.info("Number of 2D steps updated to {}".format(new_num_steps_2d))
        warning = "The voltage step between measurements ({}) is not a multiple of the voltage step between vi and vf ({}) for the 2D sweep. The number of steps should be {}".format(step_counter_2d, ramp_counter_2d, new_num_steps_2d)
        warning_string = warning_string + warning + "\n"

    if not silence_warnings and warning_string != "": # if there are warnings
        raise ValueError(warning_string)
    
    config.logger.info("2D params verification complete")

    return warning_string
    
class instruction_name:

    def __init__(self):
        self.name_cache = {}

    def unique(self, name):
        if name not in self.name_cache:
            self.name_cache[name] = 1
            return name # don't had a number at the end of the name if it is the first appearance

        else:
            self.name_cache[name] = self.name_cache[name]+1
            new_name = "{} ({})".format(name, self.name_cache[name])
            return new_name

def read_data(dig_module, digCh, pointsPerCycle, nbCycles, fullscale=2, readTimeout = 1000):
    data_array_1D = np.zeros(nbCycles)
    readPoints = 0
    for point in range(0, nbCycles):
        data = dig_module.instrument.DAQread(digCh, pointsPerCycle, readTimeout) # return a Numpy array
        readPoints = readPoints + data.size
        if len(data) == 0: # DDR underrun might cause DAQread to return no data
            break
        else:
            data_array_1D[point] = np.mean(data) * float(fullscale)/(2.**15 -1)

    return data_array_1D, readPoints

def convertFloatingPointToInteger(value_float):
    # https://stackoverflow.com/questions/53538504/float-to-binary-and-binary-to-float-in-python

    value_bin = format(struct.unpack('!I', struct.pack('!f', value_float))[0], '032b')

    value_int = int(value_bin, 2)

    return value_int

def convertVoltageToInteger(voltage_double):
    # set max and min integer values
    bitSize = 16
    maxVoltage = 1.5
    maxPositiveValue = (2 << (bitSize - 2)) - 1
    minNegativeValue = (2 << (bitSize - 1)) - 1

    # Calculate integer ([0 --> maxPositiveValue, minNegativeValue --> 0 - 1bit] = [0 --> 1.5, -1.5 --> 0 - 1bit]V)
    if voltage_double < 0:
        voltage_int = int(maxPositiveValue * voltage_double / maxVoltage) + minNegativeValue
    else:
        voltage_int = int(maxPositiveValue * voltage_double / maxVoltage)

    return voltage_int

def getVoltageFromInteger(voltage_int):
    # set max and min integer values
    bitSize = 16
    maxVoltage = 1.5
    maxPositiveValue = (2 << (bitSize - 2)) - 1 # 32767 = 2**15 - 1
    minNegativeValue = (2 << (bitSize - 1)) - 1 # 65535 = 2**16 - 1

    # Calculate integer ([0 --> maxPositiveValue, minNegativeValue --> 0 - 1bit] = [0 --> 1.5, -1.5 --> 0 - 1bit]V)
    if voltage_int > maxPositiveValue: # if negative voltage
        voltage_double = (voltage_int - minNegativeValue) * maxVoltage / maxPositiveValue
    else:
        voltage_double = voltage_int * maxVoltage / maxPositiveValue

    return voltage_double

def generateWaveformSine(ampl = 1, freq = 100e3, AWG_model = "M3201A", nCycles = 1, DIG_sampl_freq=None):
    
    # Check if AWG model is supported
    if AWG_model not in ["M3201A", "M3202A"]:
        raise ValueError("AWG model not supported. Supported models are: M3201A, M3202A")
    
    if AWG_model == "M3201A":
        AWG_sampl_freq = 500e6
    elif AWG_model == "M3202A":
        AWG_sampl_freq = 1000e6
    else:
        raise ValueError("Unknown AWG model")

    npts = int(AWG_sampl_freq/freq)*nCycles

    x = np.linspace(0, nCycles, num = npts+1)
    x = x[:-1] # Remove last point to don't repeat the same point when repeating the waveform
    y = ampl*np.sin(2*np.pi*x)

    # Change the output of the function to represent the signal measured by the digitizer
    if DIG_sampl_freq != None:
        if AWG_sampl_freq % DIG_sampl_freq != 0:
            logger.warning("Digitizer sampling frequency ({:.2e}) is not a multiple of the AWG sampling frequency ({:.2e}). The output will not have the right length.".format(DIG_sampl_freq, AWG_sampl_freq))
            
        factor = int(AWG_sampl_freq/DIG_sampl_freq)
        x = x[::factor]
        y = y[::factor]

    return x, y

def generateWaveformCosine(ampl = 1, freq = 100e3, AWG_model = "M3201A", nCycles = 1, DIG_sampl_freq=None):

    # Check if AWG model is supported
    if AWG_model not in ["M3201A", "M3202A"]:
        raise ValueError("AWG model not supported. Supported models are: M3201A, M3202A")

    if AWG_model == "M3201A":
        AWG_sampl_freq = 500e6
    elif AWG_model == "M3202A":
        AWG_sampl_freq = 1000e6
    else:
        raise ValueError("Unknown AWG model")

    npts = int(AWG_sampl_freq/freq)*nCycles

    x = np.linspace(0, nCycles, num = npts+1)
    x = x[:-1] # Remove last point to don't repeat the same point when repeating the waveform
    y = ampl*np.cos(2*np.pi*x)

    # Change the output of the function to represent the signal measured by the digitizer
    if DIG_sampl_freq != None:
        if AWG_sampl_freq % DIG_sampl_freq != 0:
            logger.warning("Digitizer sampling frequency ({:.2e}) is not a multiple of the AWG sampling frequency ({:.2e}). The output will not have the right length.".format(DIG_sampl_freq, AWG_sampl_freq))
            
        factor = int(AWG_sampl_freq/DIG_sampl_freq)
        x = x[::factor]
        y = y[::factor]

    return x, y

#%% Modular functions
def load_awg(config, awg_module: Module, reset_voltages=True):
    """
    Load the AWG firmware into the module or load the FPGA configuration if the firmware is already installed.

    Parameters
    ----------
    config : ApplicationConfig
        Configuration of the HVI program.
    awg_module : Module
        AWG module object.
    reset_voltages : bool, optional
        Reset the voltages of the AWG to zero. Useful in interactive mode. The default is True.
    
    Raises
    ------
    Exception
        If the AWG firmware loading fails.
    """
    # to do, add fly awg for virtual gates
    if config.loadBitstream == True:
        if reset_voltages:
            set_voltages_to_zero(config, awg_module)
        if not config.hardware_simulated: # don't use FPGA command in simulation mode
            logger.info("Loading {} AWG FPGA firmware in module {}".format(awg_module.firmware_to_load.name, awg_module.slot_number))
            error = awg_module.instrument.FPGAload(awg_module.firmware_to_load.path)

            if error < 0: raise Exception("AWG FPGAload error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
            logger.info('{} AWG FPGA firmware loaded into module {}'.format(awg_module.firmware_to_load.name, awg_module.slot_number))

    else:
        error = awg_module.instrument.FPGAconfigureFromK7z(awg_module.firmware_to_load.path)
        if error < 0:  raise Exception("AWG FPGAconfigureFromK7z error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
        logger.info("{} AWG FPGA firmware configured from module {}".format(awg_module.firmware_to_load.name, awg_module.slot_number))


def load_digitizer(config, digitizer_module:Module, print_registers=False):

    if config.loadBitstream == True:
        if not config.hardware_simulated: # don't use FPGA command in simulation mode
            logger.info("Loading {} digitizer FPGA firmware in module {}".format(digitizer_module.firmware_to_load.name, digitizer_module.slot_number))
            error = digitizer_module.instrument.FPGAload(digitizer_module.firmware_to_load.path)

            if error < 0: raise Exception("Digitizer FPGAload() error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
            logger.info('{} Digitizer FPGA firmware loaded into module'.format(digitizer_module.firmware_to_load.name))

    else:
        error = digitizer_module.instrument.FPGAconfigureFromK7z(digitizer_module.firmware_to_load.path)
        if error < 0:  raise Exception("Digitizer FPGAconfigureFromK7z error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
        logger.info('{} Digitizer FPGA firmware configured from module {}'.format(digitizer_module.firmware_to_load.name, digitizer_module.slot_number))


def send_CC_matrix(config, module_dict: dict, hvi: kthvi.Hvi, CC_matrix: np.array):
    """
    Send the cross-capacitance matrix to the FPGA of the AWG module for virtual gates.

    Parameters
    ----------
    config : ApplicationConfig2D class
        Experiment configuration.
    module_dict : dict
        Dictionary of the opened modules.
    CC_matrix : np.array
        Cross-capacitance matrix for virtual gates.
    
    Raises
    ------
    ValueError
        If the voltage of a channel is not zero before sending the cross-capacitance matrix.
    """
    # Check the size of the matrix
    CC_MATRIX_SIZE = (config.nb_VG_awg_modules*4)**2
    if CC_matrix.size != CC_MATRIX_SIZE:
        raise ValueError("The cross-capacitance matrix should have {} elements, not {}.".format(CC_MATRIX_SIZE, CC_matrix.size))
    
    split_CC_matrix = np.split(CC_matrix, config.nb_VG_awg_modules)
    for engine_name, awg_module in module_dict.items():
        if "AWG" in engine_name and awg_module.card_num_VG != 0:
            memory_Map = awg_module.instrument.FPGAgetSandBoxRegister(config.VG_memory_map_name)
            if isinstance(memory_Map, int):
                if memory_Map < 0:
                    error = memory_Map
                    raise Exception("AWG FPGAgetSandBoxRegisters() error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))

            config.logger.info("Sending cross-capacitance matrix to the AWG FPGA")
            vect_voltsToInt = np.vectorize(awg_module.instrument.voltsToInt)
            CC_matrix_int = vect_voltsToInt(split_CC_matrix[awg_module.card_num_VG-1].flatten()*0.75)
            config.logger.debug(CC_matrix_int)
            memory_Map.writeRegisterBuffer(0, CC_matrix_int, keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.DMA)
            config.logger.info("Cross-capacitance matrix sent to the AWG FPGA on slot {}".format(awg_module.slot_number))

            # Read the matrix to check if it was correctly sent
            # read_matrix = memory_Map.readRegisterBuffer(0, CC_matrix_int.size, keysightSD1.SD_AddressingMode.AUTOINCREMENT, keysightSD1.SD_AccessMode.DMA)
            # vect_getVoltageFromInteger= np.vectorize(getVoltageFromInteger)
            # config.logger.info(vect_getVoltageFromInteger(read_matrix)*4/3.0)

        
def define_system(config, module_dict, system_name="MySystem", sequencer_name="MySequencer"):
    # Create system definition object
    my_system = kthvi.SystemDefinition(system_name)
    # Define your system, HW platform, add HVI resources
    define_hvi_resources(my_system, module_dict, config)
    # Create sequencer object
    sequencer = kthvi.Sequencer(sequencer_name, my_system)
    
    return sequencer


def close_modules(module_dict):
    logger.info("Closing modules...")
    # Close all modules at the end of the execution
    for engine_name in module_dict:
        module_dict[engine_name].instrument.close()
    logger.info("PXI modules closed")


def initialize_reset_registers_1d(sequencer, sync_block, awg_engine_name, config):
    """
    Initialize the voltage registers with their values taken from the FPGA memory.
    """
    # Read FPGA Register Voltage Ch1 before sweep
    awg_sequence = sync_block.sequences[awg_engine_name]
    
    # Get register values
    awg_registers = sequencer.sync_sequence.scopes[awg_engine_name].registers
    voltage_channel_ch1 = awg_registers[config.voltage_ch1_name]
    voltage_channel_ch2 = awg_registers[config.voltage_ch2_name]
    voltage_channel_ch3 = awg_registers[config.voltage_ch3_name]
    voltage_channel_ch4 = awg_registers[config.voltage_ch4_name]
    voltage_register_dict = {1: voltage_channel_ch1, 2:voltage_channel_ch2, 3:voltage_channel_ch3, 4:voltage_channel_ch4}
    
    if not config.hardware_simulated:
        for ch in range(1,5):
            # Read FPGA Register Voltage before sweep
            instruction_label = config.instruction_name.unique("Read FPGA Register Bank Voltage_Ch{}".format(ch))
            readFpgaReg = awg_sequence.add_instruction(instruction_label, 100, awg_sequence.instruction_set.fpga_register_read.id)
            readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.destination.id, voltage_register_dict[ch])
            fpga_voltage_channel_name = config.fpga_voltage_chx_name.format(ch)
            fpga_voltage = awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers[fpga_voltage_channel_name]
            readFpgaReg.set_parameter(awg_sequence.instruction_set.fpga_register_read.fpga_register.id, fpga_voltage)

def set_voltages_to_zero(config, awg_module: Module, slew_rate=1):
    """
    Set the voltages of the AWG channels to zero at a given slew rate.

    Parameters
    ----------
    config : ApplicationConfig2D
        Experiment configuration.
    awg_module : Module
        AWG module object.
    slew_rate : float, optional
        Slew rate of the voltage change. The default is 1.
    
    Raises
    ------
    ValueError
        If the slew rate is not between 0.1 and 1 V/s.
    ValueError
        If the requested voltage is higher than 1.5 V.
    """
    # Check that slew rate is between 0.1 and 1 V/s
    if slew_rate < 0.1 or slew_rate > 1: raise ValueError("Slew rate should be between 0.1 and 1 V/s.")
        
    config.logger.info("Resetting all AWG channels to 0 V at {:.02f} V/s".format(slew_rate))
    VOLTAGE_STEP = 0.01
    INTERNAL_VOLTAGE_STEP = VOLTAGE_STEP/2.0
    for i in range(awg_module.num_channels):
        voltage, voltage_int = read_channel_voltage(i+1, awg_module)
        internal_voltage = voltage/2.0

        while abs(voltage) > 1e-3:
            if abs(voltage) < 0.01:
                requested_voltage = 0
            elif voltage > 0:
                requested_voltage = (internal_voltage - INTERNAL_VOLTAGE_STEP)
            else:
                requested_voltage = (internal_voltage + INTERNAL_VOLTAGE_STEP)

            if requested_voltage > 1.5:
                raise ValueError("Requested voltage ({:.03f} V) is higher than 1.5 V.".format(requested_voltage))
            else:
                awg_module.instrument.channelOffset(i+1, requested_voltage)
            
            voltage, voltage_int = read_channel_voltage(i+1, awg_module)
            internal_voltage = voltage/2.0
            time.sleep(VOLTAGE_STEP/slew_rate)


def sweep_voltage_register(config, register, target_value, slew_rate=1):
    config.logger.info("Sweeping register {} to {} ({:.05f} V HiZ) at {:.02f} V/s".format(register.Name.rstrip("\x00"), target_value, getVoltageFromInteger(target_value)*2, slew_rate))
    # Check that slew rate is between 0.1 and 1 V/s
    if slew_rate < 0.1 or slew_rate > 1: raise ValueError("Slew rate should be between 0.1 and 1 V/s.")
        
    VOLTAGE_STEP = 0.01
    INTERNAL_VOLTAGE_STEP = VOLTAGE_STEP/2.0

    register_int = int(register.readRegisterInt32())
    register_internal_voltage = getVoltageFromInteger(register_int)
    target_internal_voltage = getVoltageFromInteger(target_value)

    # Bring the register value within less than a step from the target value
    while abs(register_internal_voltage - target_internal_voltage) > INTERNAL_VOLTAGE_STEP:
        if register_internal_voltage > target_internal_voltage:
            requested_voltage = (register_internal_voltage - INTERNAL_VOLTAGE_STEP)
        else:
            requested_voltage = (register_internal_voltage + INTERNAL_VOLTAGE_STEP)

        if abs(requested_voltage) > 1.5:
            raise ValueError("Requested voltage ({:.03f} V) is higher than 1.5 V.".format(requested_voltage))
        else:
            requested_value = convertVoltageToInteger(requested_voltage)
            error = register.writeRegisterInt32(int(requested_value))
            if error < 0: raise Exception("Register write error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
        
        # Update the register value
        register_int = int(register.readRegisterInt32())
        register_internal_voltage = getVoltageFromInteger(register_int)
        time.sleep(VOLTAGE_STEP/slew_rate)

    # Set the register to the target value
    error = register.writeRegisterInt32(int(target_value))
    if error < 0: raise Exception("Register write error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))


def update_vg_registers(config, module_dict: dict, hvi: kthvi.Hvi):
    config.logger.info("Checking if all registers for the virtual gates are up to date.")
    NB_CHANNELS_PER_MODULE = 4 # assuming 4 channels per VG module
    vg_modules = []
    vg_ch_voltages = [] # ordered fron vg1 to vg4, vg8 or vg12

    # Get AWG_channel_1d and AWG_channel_2d values from the main and secondary AWG modules
    main_awg_module = module_dict[config.main_awg_engine_name]
    secondary_awg_module = module_dict[config.secondary_awg_engine_name]

    v_1d, v_1d_int = read_channel_voltage(config.AWG_channel_1d, main_awg_module, HZ=False)
    v_2d, v_2d_int = read_channel_voltage(config.AWG_channel_2d, secondary_awg_module, HZ=False)

    # Update register banks in PathWave FPGA used for virtual gates
    for vg_module_descriptor in config.vg_module_descriptor_list:
        # Update virtual gates modules' sweep registers in HVI
        awg_registers = hvi.sync_sequence.scopes[vg_module_descriptor.engine_name].registers
        voltage_channel_1d = awg_registers[config.voltage_1d_name.format(config.AWG_channel_1d)]
        voltage_channel_2d = awg_registers[config.voltage_2d_name.format(config.AWG_channel_2d)]
        voltage_channel_1d.write(v_1d_int)
        voltage_channel_2d.write(v_2d_int)

        vg_module = module_dict[vg_module_descriptor.engine_name]
        vg_modules.append(vg_module)

        for ch in range(1, vg_module.num_channels+1):
            voltage, voltage_int = read_channel_voltage(ch, vg_module, HZ=False)
            vg_ch_voltages.append(voltage_int)

    vg_ch_voltages = np.array(vg_ch_voltages)
    config.logger.info("Voltage values: \n{}".format(vg_ch_voltages))

    for module_index, vg_module in enumerate(vg_modules):
        for ch_index in range((config.nb_VG_awg_modules*NB_CHANNELS_PER_MODULE)-NB_CHANNELS_PER_MODULE):
            start_ch_index = (module_index+1)*NB_CHANNELS_PER_MODULE # don't update the registers of the current module since it has its own voltages already, update the n-1 next modules
            ch_to_update_index = (start_ch_index+ch_index)%(config.nb_VG_awg_modules*NB_CHANNELS_PER_MODULE)
            module_to_update_index = ((start_ch_index+ch_index)//(NB_CHANNELS_PER_MODULE))%config.nb_VG_awg_modules
            register_name = "Voltage_card{}_host_V_ch{}".format(module_to_update_index+1, ch_to_update_index+1)
            register = vg_module.instrument.FPGAgetSandBoxRegister(register_name)
            if isinstance(register, int) and register < 0: raise Exception("AWG FPGAgetSandBoxRegister() error {}: {}. Can't find register {} in {}.".format(register, keysightSD1.SD_Error.getErrorMessage(register), register_name, vg_module.engine_name))
            register_int = int(register.readRegisterInt32())
            config.logger.info("Checking {} on {}".format(register_name,  vg_module.engine_name))
            # config.logger.info(vg_ch_voltages[ch_to_update_index], vg_register_values[module_index,ch_index])
            
            if vg_ch_voltages[ch_to_update_index] != register_int:
                config.logger.info("Updating register bank card{}, ch{} to {}".format(module_to_update_index+1, ch_to_update_index+1, vg_ch_voltages[ch_to_update_index]))
                sweep_voltage_register(config, register, vg_ch_voltages[ch_to_update_index])

    config.logger.info("All voltage registers are up to date.")


def read_channel_voltage(channel, awg_module: Module, HZ=True):
    """
    Read the voltage of a channel on the FPGA.

    Parameters
    ----------
    channel : int
        Channel number.
    awg_module : Module
        AWG module object.
    HZ : bool, optional
        If True, the AWG channel is connected to a high impedance load. The default is True.

    Returns
    -------
    voltage : float
        Voltage of the channel after conversion.
    voltage_int : int
        Integer value of the voltage before conversion.
    """
    # Read register with SD1
    register_name = "Voltage_registers_host_V_Ch{}".format(channel)
    register = awg_module.instrument.FPGAgetSandBoxRegister(register_name)
    if isinstance(register, int) and register < 0:
        error = register
        raise Exception("AWG FPGAgetSandBoxRegister() error {}: {}. The firmware might not be loaded.".format(error, keysightSD1.SD_Error.getErrorMessage(error)))

    voltage_int = int(register.readRegisterInt32())
    max_voltage = 1.5
    if HZ:
        correction_factor = 2.0
    else:
        correction_factor = 1.0
    voltage = round(getVoltageFromInteger(voltage_int)*correction_factor, 6)

    return voltage, voltage_int

def initialize_logging(folder_name, log_file_name):
    """
    Initialize logging for the application.

    Parameters
    ----------
    folder_name : str
        Name of the folder where to save the logs.
    
    Returns
    -------
    logger : logging.Logger
        Logger object.
    console_handler : logging.Handler
        Console handler.
    file_handler : logging.Handler
        File handler.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    log_dir = folder_name
    logger, console_handler, file_handler = quick_config(logger, file_fmt='%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s: %(message)s', file_log_dir=log_dir, log_file_name=log_file_name, logger_blacklist=["matplotlib.font_manager", "matplotlib.colorbar", "parso.python.diff"])
    logger.debug('Logging initialized')

    return logger, console_handler, file_handler

def stop_logging(logger, console_handler, file_handler):
    """
    Stop logging for the application.

    Parameters
    ----------
    logger : logging.Logger
        Logger object.
    """

    console_handler.close()
    logger.removeHandler(console_handler)
    file_handler.close()
    logger.removeHandler(file_handler)

def release_all_modules(config):
    """
    Stop HVI is it is running, release HW resources and close all modules.
    To be used in interactive mode. 

    Parameters
    ----------
    config : ApplicationConfig1D or ApplicationConfig2D
        Configuration of the HVI program.
    """
    if "hvi" in globals() or "hvi" in locals():
        if hvi.is_running():
            hvi.stop()
            config.logger.info("HVI stopped")
        # Release HW resources once HVI execution is completed
        hvi.release_hw()
        config.logger.info("Releasing HW...")
    
    # Close all modules at the end of the execution
    if "module_dict" in globals() or "module_dict" in locals():
        for engine_name in module_dict:
            module_dict[engine_name].instrument.close()
        config.logger.info("PXI modules closed")

def calc_num_cycles_per_segment(num_cycles, points_per_cycle, use_QD_emulator=False) -> Tuple[int, int]:
    """
    Calculate the number of cycles per measurement segment and the number of segments.
    The number of cycles per segment is calculated to avoid reaching the maximum number of points that can be acquired in one go.

    Parameters
    ----------
    num_cycles : int
        Number of cycles to acquire.
    points_per_cycle : int
        Number of points per cycle.
    
    Returns
    -------
    cycles_per_segment : int
        Number of cycles per segment.
    num_segments : int
        Number of segments.
    """
    if use_QD_emulator:
        POINTS_THRESHOLD = 10000000 # to be tested, timeout is time related rather than the number of points measured
    else:
        POINTS_THRESHOLD = 1000000000 # actual limit is around 2^32
    acquisition_points = num_cycles*points_per_cycle

    if acquisition_points > POINTS_THRESHOLD:
        num_segments = int(np.ceil(acquisition_points/POINTS_THRESHOLD))
        cycles_per_segment = int(np.ceil(num_cycles/num_segments))
              
        if cycles_per_segment*num_segments < num_cycles:
            raise ValueError("The number of cycles per segment ({}) times the number of segments ({}) is less than the number of cycles ({}).".format(cycles_per_segment, num_segments, num_cycles))
    else:
        cycles_per_segment = num_cycles
        num_segments = 1

    return cycles_per_segment, num_segments

