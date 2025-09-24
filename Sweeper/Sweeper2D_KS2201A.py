import sys
import numpy as np
import time
import matplotlib.pyplot as plt
import os
import gc
import yaml
import shutil
import inspect
try:
    import pyqtgraph as pqt
    from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
    PYQTGRAPH_INSTALLED = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets # can replace pyqtgraph
    PYQTGRAPH_INSTALLED = False
from matplotlib.widgets import Button
from threading import Event
from generic_logging import quick_config
import logging
sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1
try:
    import keysight_tse as kthvi
except ImportError:
    import keysight_hvi as kthvi
from Sweeper1D_KS2201A import sweeper_1d, initialize_awg_registers_1d, initialize_dig_registers_1d, ApplicationConfig1D, \
                                define_awg_registers_1d, define_dig_registers_1d, update_awg_registers_1d, update_dig_registers_1d
from KS2201A_lib import ModuleDescriptor, Module, open_modules, configure_awg, configure_digitizer, \
                        calc_step_counter, program_step_to_target_voltage, export_hvi_sequences, \
                        load_awg, load_digitizer, send_CC_matrix, define_system, set_voltages_to_zero, \
                        read_channel_voltage, verify_sweep_parameters_1d, verify_sweep_parameters_2d, \
                        set_hvi_done, initialize_logging, calc_num_cycles_per_segment, update_vg_registers 
                        
from file_save_system import create_save_filename

#%% Config
class ApplicationConfig2D(ApplicationConfig1D):
    " Defines module descriptors, configuration options and names of HVI engines, actions, triggers"
    def __init__(self, log_dir, chassis_list, module_descriptors, vi_1d, vf_1d, num_steps_1d, vi_2d, vf_2d, num_steps_2d, AWG_channel_1d=1, slew_rate_1d=1, AWG_channel_2d=2, slew_rate_2d=1, integration_time = 10000, prescaler=4, dV=45.7778e-6,
                 loadBitstream=False, load_digitizer_channel_config = False, use_QD_emulator = False, QD_emulator_Cm=0.2, use_virtual_gates=False, hardware_simulated=False, start_logging=True):
        
        if start_logging:
            day_folder, _ = create_save_filename(log_dir, "Sweeper2D")
            self.logger, self.console_handler, self.file_handler = initialize_logging(day_folder, "Sweeper2D")

        # 1D sweep parameters
        ApplicationConfig1D.__init__(self, log_dir, chassis_list, module_descriptors, vi_1d, vf_1d, num_steps_1d, AWG_channel_1d, slew_rate_1d, integration_time, prescaler, dV,
                                     loadBitstream, load_digitizer_channel_config, use_QD_emulator, QD_emulator_Cm, use_virtual_gates, hardware_simulated, start_logging=False)

        """
        Define names of HVI engines, actions, registers
        """
        # HVI engine names to be used in this application
        self.secondary_awg_engine_name = None
        self.third_awg_engine_name = None
        self.fourth_awg_engine_name = None

        # 2D sweep parameters
        # HVI register names to be used within the scope of each HVI engine
        self.vi_2d_name = "Vi 2D"
        self.vf_2d_name = "Vf 2D"
        self.voltage_2d_name = "Voltage 2D (Ch{})"
        self.vg_voltage_2d_name = "VG Voltage 2D (Ch{})" # used to save the voltage set by the sweeping module for virtual gates

        self.step_counter_2d_name = "Step Counter 2D"
        self.loop_counter_2d_name = "Loop Counter 2D"
        self.ramp_counter_2d_name = "Ramp Counter 2D"
        self.awg_loop_counter_2d_name = "AWG Loop Counter 2D"

        self.num_cycles_seg_name = "Num Cycles per segment"
        self.num_cycles_since_config_name = "Num Cycles since config"

        """
        Defines the experiment parameters
        """
        self.AWG_channel_2d = AWG_channel_2d
        self.vi_2d = vi_2d
        self.vf_2d = vf_2d
        self.slew_rate_2d = slew_rate_2d # [V/s]
        self.num_steps_2d = num_steps_2d

    @classmethod
    def from_yaml(cls, yaml_file, logger=None):
        with open(yaml_file, 'r') as file:
            data = yaml.safe_load(file)

        awg_descriptor_names = [key for key in data.keys() if "awg_descriptor" in key] 
        all_descritptor_names = [key for key in data.keys() if "descriptor" in key] # ["main_awg_descriptor", "secondary_awg_descriptor", "third_awg_descriptor", "fourth_awg_descriptor", "digitizer_descriptor"]
        nb_awg_descriptors = len(awg_descriptor_names)
        extra_awg_descriptor_names = ["third_awg_descriptor", "fourth_awg_descriptor"]

        config_data = data["ApplicationConfig"]
        log_dir = config_data["log_dir"]

        # Get expected arguments from class
        expected_args = inspect.getfullargspec(cls.__init__).args

        # Remove excess arguments from config_data
        new_config_data = {key: config_data[key] for key in expected_args if key != "self" and key != "chassis_list" and key != "module_descriptors" and key != "start_logging"}
            
        # Create chassis_list
        chassis_list = sorted(list(set([data[descriptor]["chassis_number"] for descriptor in all_descritptor_names]))) # remove duplicates with set

        # Define main AWG and secondary engine names
        main_awg_descriptor = ModuleDescriptor.from_dict(data["main_awg_descriptor"])
        secondary_awg_descriptor = ModuleDescriptor.from_dict(data["secondary_awg_descriptor"])
        dig_descriptor = ModuleDescriptor.from_dict(data["digitizer_descriptor"])

        module_descriptors = []
        third_awg_engine_name = None
        fourth_awg_engine_name = None
        # Create module_descriptors
        for name in all_descritptor_names:
            module_descriptor = ModuleDescriptor.from_dict(data[name])
            if main_awg_descriptor.engine_name == secondary_awg_descriptor.engine_name and name == "secondary_awg_descriptor":
                continue # don't add the secondary_awg_descriptor if it's the same module as the main_awg_descriptor
            if config_data["use_virtual_gates"] == False and name in extra_awg_descriptor_names:
                continue # don't add the extra awg_descriptors if virtual gates are not used
            if config_data["use_virtual_gates"] == True and name in extra_awg_descriptor_names:
                if module_descriptor.card_num_VG == 0:
                    continue # don't add the module if it's not used for virtual gates
                if name == "third_awg_descriptor":
                    third_awg_engine_name = module_descriptor.engine_name
                if name == "fourth_awg_descriptor":
                    fourth_awg_engine_name = module_descriptor.engine_name
            
            module_descriptors.append(module_descriptor)

        # Check how many AWG modules are used for virtual gates
        nb_VG_awg_modules = 0
        for module in module_descriptors:
            if "AWG" in module.engine_name:
                if module.card_num_VG > 0:
                    nb_VG_awg_modules += 1

        if main_awg_descriptor.engine_name == secondary_awg_descriptor.engine_name:
            # There will be 2 descriptors for the same module. Therefore, there will be 4 descriptors for 3 modules.
            MAX_VG_AWG_DESCRIPTORS = 4
        else:
            MAX_VG_AWG_DESCRIPTORS = 3
        if nb_VG_awg_modules > MAX_VG_AWG_DESCRIPTORS: raise ValueError("Only a maximum of 3 AWG modules can be used for virtual gates.")

        # Check that there is no duplicate virtual gate modules
        if bool(data["ApplicationConfig"]["use_virtual_gates"]):
            vg_card_number_list = [module_descriptor.card_num_VG for module_descriptor in module_descriptors if "AWG" in module_descriptor.engine_name]
            if len(vg_card_number_list) != len(set(vg_card_number_list)):
                raise ValueError("card_num_VG must be unique for each module.")



        config = cls(log_dir, chassis_list, module_descriptors, new_config_data["vi_1d"], new_config_data["vf_1d"], new_config_data["num_steps_1d"], new_config_data["vi_2d"], new_config_data["vf_2d"], new_config_data["num_steps_2d"], new_config_data["AWG_channel_1d"], new_config_data["slew_rate_1d"], new_config_data["AWG_channel_2d"], new_config_data["slew_rate_2d"], new_config_data["integration_time"], new_config_data["prescaler"], new_config_data["dV"], new_config_data["loadBitstream"], new_config_data["load_digitizer_channel_config"], new_config_data["use_QD_emulator"], new_config_data["QD_emulator_Cm"], new_config_data["use_virtual_gates"], new_config_data["hardware_simulated"])
        if logger is not None:
            config.logger = logger
        warnings = verify_sweep_parameters_1d(config, silence_warnings=True, auto_fix=True)
        config.logger.info("1D sweep parameters warnings: {}".format(warnings))
        warnings = verify_sweep_parameters_2d(config, silence_warnings=True, auto_fix=True)
        config.logger.info("2D sweep parameters warnings: {}".format(warnings))
        if config.use_virtual_gates:
            config.logger.info("Using {} AWG modules for virtual gates.".format(nb_VG_awg_modules))


        config.main_awg_engine_name = main_awg_descriptor.engine_name
        if main_awg_descriptor.engine_name == secondary_awg_descriptor.engine_name:
            config.secondary_awg_engine_name = main_awg_descriptor.engine_name
        else:
            config.secondary_awg_engine_name = secondary_awg_descriptor.engine_name
        config.main_dig_engine_name = dig_descriptor.engine_name
        config.third_awg_engine_name = third_awg_engine_name
        config.fourth_awg_engine_name = fourth_awg_engine_name

        # Define database_folder, save_filename and other parameters
        config.database_folder = config_data["database_folder"]
        config.save_filename = config_data["save_filename"]
        config.max_time = config_data["max_time"]
        config.stabilization_time = config_data["stabilization_time"]
        config.fullscale = config_data["fullscale"]

        # Add number of virtual gates modules to config
        config.nb_VG_awg_modules = nb_VG_awg_modules

        # Keep track of the number of AWG modules used for virtual gates
        if config.use_virtual_gates:
            config.vg_module_descriptor_list = sorted([module_descriptor for module_descriptor in module_descriptors if "AWG" in module_descriptor.engine_name and module_descriptor.card_num_VG > 0], key=lambda module_descriptor: module_descriptor.card_num_VG)

        # Update yaml file with verified_num_steps_1d
        with open(yaml_file, 'r+') as file:
            lines = file.readlines()
            for i, line in enumerate(lines):
                if "verified_num_steps_1d" in line:
                    split_line = line.split(":")
                    split_value = split_line[1].split(" ") # verified_num_steps_1d = split_value[1]

                    # Recombine the split line
                    split_value[1] = str(config.num_steps_1d)
                    split_line[1] = " ".join(split_value)
                    lines[i] = ":".join(split_line)

                if "verified_num_steps_2d" in line:
                    split_line = line.split(":")
                    split_value = split_line[1].split(" ") # verified_num_steps_2d = split_value[1]

                    # Recombine the split line
                    split_value[1] = str(config.num_steps_2d)
                    split_line[1] = " ".join(split_value)
                    lines[i] = ":".join(split_line)

            # Write the updated lines to the file
            file.seek(0)
            file.writelines(lines)

        # Add YAML config filename to config
        config.yaml_file = yaml_file

        return config
    
    @property
    def vi_2d_internal(self):
        # Divide by 2 since AWG is outputing twice the voltage on HZ loads
        return self.vi_2d/2.0
    @property
    def vf_2d_internal(self):
        # Divide by 2 since AWG is outputing twice the voltage on HZ loads
        return self.vf_2d/2.0

    @property
    def num_cycles(self):
        return self.num_steps_1d*self.num_steps_2d # insert -1 for infinite cycles

    def __str__(self):
        return  "chassis_list={}, module_descriptors={}\n" \
                "ApplicationConfig1D: vi_1d={}, vf_1d={}, num_steps_1d={}, AWG_channel_1d={}, slew_rate_1d={}, integration_time={}, stabilization_time={}, dig_prescaler={}, dV={}, loadBitstream={}, load_digitizer_channel_config={}, use_QD_emulator={}, QD_emulator_Cm={}, use_virtual_gates={}, hardware_simulated={}\n" \
                "ApplicationConfig2D: vi_2d={}, vf_2d={}, num_steps_2d={}, AWG_channel_2d={}, slew_rate_2d={}".format(
                self.chassis_list, self.module_descriptors,
                self.vi_1d, self.vf_1d, self.num_steps_1d, self.AWG_channel_1d, self.slew_rate_1d, self.integration_time, self.stabilization_time, self.dig_prescaler, self.dV, self.loadBitstream, self.load_digitizer_channel_config, self.use_QD_emulator, self.QD_emulator_Cm, self.use_virtual_gates, self.hardware_simulated,
                self.vi_2d, self.vf_2d, self.num_steps_2d, self.AWG_channel_2d, self.slew_rate_2d)
    
    def __del__(self):
        self.console_handler.close()
        self.logger.removeHandler(self.console_handler)
        self.file_handler.close()
        self.logger.removeHandler(self.file_handler)

#%% 2nd Level: Functions to Define, Program, Execute HVI
########################################################

def define_awg_registers_2d(sequencer, awg_module, config):
    """
    Define the AWG registers for the module's HVI engine in the scope of the global sync sequence.

    Parameters
    ----------
    sequencer : kthvi.Sequencer object
        HVI sequence definition.
    dig_module : Module
        Digitizer module object.
    config : ApplicationConfig2D
        Configuration of the HVI program.
    """
    awg_engine_name = awg_module.engine_name
    
    # AWG registers
    # voltage 2D
    sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.voltage_2d_name.format(config.AWG_channel_2d), kthvi.RegisterSize.SHORT)
    sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.vg_voltage_2d_name.format(config.AWG_channel_2d), kthvi.RegisterSize.SHORT)

    vi_2d = sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.vi_2d_name, kthvi.RegisterSize.SHORT)
    vi_2d.initial_value = awg_module.instrument.voltsToInt(config.vi_2d_internal)
    vf_2d = sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.vf_2d_name, kthvi.RegisterSize.SHORT)
    vf_2d.initial_value = awg_module.instrument.voltsToInt(config.vf_2d_internal)

    config.logger.info("Vi 2d: {}={}".format(config.vi_2d_internal, awg_module.instrument.voltsToInt(config.vi_2d_internal)))
    config.logger.info("Vf 2d: {}={}".format(config.vf_2d_internal, awg_module.instrument.voltsToInt(config.vf_2d_internal)))
    config.logger.info("Num steps 2d: {}".format(config.num_steps_2d))

    awg_loop_counter_2d = sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.awg_loop_counter_2d_name, kthvi.RegisterSize.SHORT)
    awg_loop_counter_2d.initial_value = 0
    ramp_counter_2d = sequencer.sync_sequence.scopes[awg_engine_name].registers.add(config.ramp_counter_2d_name, kthvi.RegisterSize.SHORT)
    ramp_counter_2d_value = calc_step_counter(config.vi_2d_internal, config.vf_2d_internal, 2, dV=config.dV)
    ramp_counter_2d.initial_value = ramp_counter_2d_value
    config.logger.info("Ramp counter 2d: {}".format(ramp_counter_2d_value))

def define_dig_registers_2d(sequencer, dig_module, config):
    """
    Update the 2D sweep digitizer registers of the module's HVI engine in the scope of the global sync sequence.

    Parameters
    ----------
    hvi : kthvi.Hvi
        HVI object.
    dig_module : Module
        Digitizer module object.
    config : ApplicationConfig2D
        Configuration of the HVI program.
    """
    dig_engine_name = dig_module.engine_name

    # Digitizer registers
    loop_counter_2d = sequencer.sync_sequence.scopes[dig_engine_name].registers.add(config.loop_counter_2d_name, kthvi.RegisterSize.SHORT)
    loop_counter_2d.initial_value = 0

    step_counter_2d = sequencer.sync_sequence.scopes[dig_engine_name].registers.add(config.step_counter_2d_name, kthvi.RegisterSize.SHORT)
    step_counter_2d.initial_value = calc_step_counter(config.vi_2d_internal, config.vf_2d_internal, config.num_steps_2d, dV=config.dV)
    config.logger.info("Step counter 2d: {}".format(calc_step_counter(config.vi_2d_internal, config.vf_2d_internal, config.num_steps_2d, dV=config.dV)))

    
    
def update_awg_registers_2d(hvi, awg_module, config, module_dict):
    """
    Update the 2D sweep AWG registers of the module's HVI engine in the scope of the global sync sequence.

    Parameters
    ----------
    hvi : kthvi.Hvi
        HVI object.
    awg_module : Module
        AWG module object.
    config : ApplicationConfig2D
        Configuration of the HVI program.
    module_dict : dict
        Dictionary containing all the modules used in the HVI program. Used here only for virtual gates.
    """
    awg_engine_name = awg_module.engine_name

    # AWG registers
    vi_2d = hvi.sync_sequence.scopes[awg_engine_name].registers[config.vi_2d_name]
    vi_2d.initial_value = awg_module.instrument.voltsToInt(config.vi_2d_internal)
    vf_2d = hvi.sync_sequence.scopes[awg_engine_name].registers[config.vf_2d_name]
    vf_2d.initial_value = awg_module.instrument.voltsToInt(config.vf_2d_internal)

    if config.use_virtual_gates:
        main_awg_module = module_dict[config.main_awg_engine_name]
        v_1d, v_1d_int = read_channel_voltage(config.AWG_channel_1d, main_awg_module, HZ=False)
        vg_v_1d = hvi.sync_sequence.scopes[awg_engine_name].registers[config.vg_voltage_1d_name.format(config.AWG_channel_1d)]
        vg_v_1d.initial_value = v_1d_int

        # Update the voltage register on the vg modules
        for vg_module_descriptor in config.vg_module_descriptor_list:
            vg_v_1d = hvi.sync_sequence.scopes[vg_module_descriptor.engine_name].registers[config.vg_voltage_1d_name.format(config.AWG_channel_1d)]
            vg_v_1d.initial_value = v_1d_int


    awg_loop_counter_2d = hvi.sync_sequence.scopes[awg_engine_name].registers[config.awg_loop_counter_2d_name]
    awg_loop_counter_2d.initial_value = 0
    ramp_counter_2d = hvi.sync_sequence.scopes[awg_engine_name].registers[config.ramp_counter_2d_name]
    ramp_counter_2d.initial_value = calc_step_counter(config.vi_2d_internal, config.vf_2d_internal, 2, dV=config.dV)

def update_dig_registers_2d(hvi, dig_module, config):
    """
        Defines all registers for each HVI engine in the scope af the global sync sequence
    """
    dig_engine_name = dig_module.engine_name

    # Digitizer registers
    loop_counter_2d = hvi.sync_sequence.scopes[dig_engine_name].registers[config.loop_counter_2d_name]
    loop_counter_2d.initial_value = 0

    step_counter_2d = hvi.sync_sequence.scopes[dig_engine_name].registers[config.step_counter_2d_name]
    step_counter_2d.initial_value = calc_step_counter(config.vi_2d_internal, config.vf_2d_internal, config.num_steps_2d, dV=config.dV)


def initialize_dig_registers_2d(dig_sequence, config):
    """
    Initialize previously defined digitizer registers
    """
    if config.use_QD_emulator and not config.hardware_simulated:
        writeMemoryMap = dig_sequence.add_instruction("Write reg_HLS_start = 1", 30, dig_sequence.instruction_set.fpga_array_write.id)
        fpga_memory_map_DIG = dig_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_memory_maps[config.MemoryEngine_QD_emulator_name]
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map.id, fpga_memory_map_DIG)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map_offset.id, 0)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.value.id, 1)

        writeMemoryMap = dig_sequence.add_instruction("Set Cm value", 10, dig_sequence.instruction_set.fpga_array_write.id)
        fpga_memory_map_DIG = dig_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_memory_maps[config.MemoryEngine_QD_emulator_name]
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map.id, fpga_memory_map_DIG)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map_offset.id, 8)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.value.id, dig_sequence.scope.registers[config.Cm_value_name])
    
def initialize_awg_registers_2d(sync_block, secondary_awg_module, config):

    secondary_awg_engine_name = secondary_awg_module.engine_name
    secondary_awg_sequence = sync_block.sequences[secondary_awg_engine_name]

    awg_registers = secondary_awg_sequence.scope.registers
    voltage_channel_2d = awg_registers[config.voltage_2d_name.format(config.AWG_channel_2d)] 
    
    if not config.hardware_simulated:
        # Read FPGA Register Voltage 2D before sweep
        instruction_label = config.instruction_name.unique("Read FPGA Register Bank Voltage_Chx (2D)")
        readFpgaReg = secondary_awg_sequence.add_instruction(instruction_label, 100, secondary_awg_sequence.instruction_set.fpga_register_read.id)
        readFpgaReg.set_parameter(secondary_awg_sequence.instruction_set.fpga_register_read.destination.id, voltage_channel_2d)
        fpga_voltage_channel_name = config.fpga_voltage_chx_name.format(config.AWG_channel_2d)
        fpga_voltage = secondary_awg_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_registers[fpga_voltage_channel_name]
        readFpgaReg.set_parameter(secondary_awg_sequence.instruction_set.fpga_register_read.fpga_register.id, fpga_voltage)

    
def sweeper_2d(sequencer, config, awg_module: Module, dig_module: Module, secondary_awg_module: Module, virtual_gates_modules=[]):
    """    
    This method programs the HVI sequence for a 2D voltage sweep.
    Different HVI statements are encapsulated as much as possible in separated SW methods to help users visualize
    the programmed HVI sequences.

    Parameters
    ----------
    sequencer : kthvi.Sequencer object
        HVI sequence definition.
    config : ApplicationConfig2D class
        Experiment configuration.
    awg_module : Module object
        AWG module used for the 1D sweep.
    dig_module : Module object
        Digitizer module used for the measurement.
    secondary_awg_module : Module object
        Secondary AWG module used for the 2D sweep.
    virtual_gates_modules : list of Module objects, optional
        List of modules used for the virtual gates excluding the awg_module and secondary_awg_module, by default [].
    """    

    awg_engine_name = awg_module.engine_name
    dig_engine_name = dig_module.engine_name
    secondary_awg_engine_name = secondary_awg_module.engine_name

    # Get register values
    secondary_awg_registers = sequencer.sync_sequence.scopes[secondary_awg_engine_name].registers
    voltage_channel_2d = secondary_awg_registers[config.voltage_2d_name.format(config.AWG_channel_2d)] 
    vi_2d = secondary_awg_registers[config.vi_2d_name]
    vf_2d = secondary_awg_registers[config.vf_2d_name]
    awg_loop_counter_2d = secondary_awg_registers[config.awg_loop_counter_2d_name]
    ramp_counter_2d = secondary_awg_registers[config.ramp_counter_2d_name]

    dig_registers = sequencer.sync_sequence.scopes[dig_engine_name].registers
    loop_counter_2d = dig_registers[config.loop_counter_2d_name]
    step_counter_2d = dig_registers[config.step_counter_2d_name]
    
    ###########################################################################
    
    # Configure Sync While Condition
    sync_while_condition = kthvi.Condition.register_comparison(voltage_channel_2d, kthvi.ComparisonOperator.NOT_EQUAL_TO, vi_2d)
    instruction_label = config.instruction_name.unique("While Voltage Chx != Vi 2D")
    sync_while_init = sequencer.sync_sequence.add_sync_while(instruction_label, 320, sync_while_condition)

    # Add a sync block
    instruction_label = config.instruction_name.unique("Go to Vi 2D")
    sync_block = sync_while_init.sync_sequence.add_sync_multi_sequence_block(instruction_label, 260)
    awg_sequence = sync_block.sequences[awg_engine_name]
    secondary_awg_sequence = sync_block.sequences[secondary_awg_engine_name]

    voltage_channel = sequencer.sync_sequence.scopes[secondary_awg_engine_name].registers[config.voltage_2d_name.format(config.AWG_channel_2d)]
    program_step_to_target_voltage(sequencer, secondary_awg_module, secondary_awg_sequence, config, config.AWG_channel_2d, voltage_channel, vi_2d, config.slew_rate_2d, use_dV_from_config=False, output_voltage=True)
    # If virtual gates are used, update the swept voltage on the other modules
    # If the 2D sweep is done with two AWG modules, update the voltage register on the other module used for sweeping
    if config.use_virtual_gates and config.main_awg_engine_name != config.secondary_awg_engine_name:
        voltage_channel = sequencer.sync_sequence.scopes[awg_module.engine_name].registers[config.vg_voltage_2d_name.format(config.AWG_channel_2d)]
        vi_2d = sequencer.sync_sequence.scopes[awg_module.engine_name].registers[config.vi_2d_name]
        program_step_to_target_voltage(sequencer, awg_module, awg_sequence, config, config.AWG_channel_2d, voltage_channel, vi_2d, config.slew_rate_2d, use_dV_from_config=False, output_voltage=False, source_VG_module=secondary_awg_module)
    # Update the voltage register on the other modules
    for virtual_gate_module in virtual_gates_modules:
        voltage_channel = sequencer.sync_sequence.scopes[virtual_gate_module.engine_name].registers[config.vg_voltage_2d_name.format(config.AWG_channel_2d)]
        vi_2d = sequencer.sync_sequence.scopes[virtual_gate_module.engine_name].registers[config.vi_2d_name]
        program_step_to_target_voltage(sequencer, virtual_gate_module, sync_block.sequences[virtual_gate_module.engine_name], config, config.AWG_channel_2d, voltage_channel, vi_2d, config.slew_rate_2d, use_dV_from_config=False, output_voltage=False, source_VG_module=secondary_awg_module)

    if config.use_virtual_gates and (awg_engine_name != secondary_awg_engine_name):
        sweeper_1d(sequencer, awg_module, dig_module, config, virtual_gates_modules=[secondary_awg_module]+virtual_gates_modules)
    else:
        sweeper_1d(sequencer, awg_module, dig_module, config, virtual_gates_modules=virtual_gates_modules)

    # Configure Sync While Condition
    sync_while_condition = kthvi.Condition.register_comparison(awg_loop_counter_2d, kthvi.ComparisonOperator.LESS_THAN, ramp_counter_2d)
    instruction_label = config.instruction_name.unique("While AWG loop counter 2D < ramp counter 2D")
    outer_sync_while_loop = sequencer.sync_sequence.add_sync_while(instruction_label, 320, sync_while_condition)

    # Add a sync block
    instruction_label = config.instruction_name.unique("Loop 2D")
    sync_block = outer_sync_while_loop.sync_sequence.add_sync_multi_sequence_block(instruction_label, 510)
    dig_sequence = sync_block.sequences[dig_engine_name]
    
    instruction_label = config.instruction_name.unique("LoopCounter 2D = 0")
    instruction = dig_sequence.add_instruction(instruction_label, 10, dig_sequence.instruction_set.assign.id)
    instruction.set_parameter(dig_sequence.instruction_set.assign.destination.id, loop_counter_2d)
    instruction.set_parameter(dig_sequence.instruction_set.assign.source.id, 0)
    
    # Configure Sync While Condition
    sync_while_condition = kthvi.Condition.register_comparison(loop_counter_2d, kthvi.ComparisonOperator.NOT_EQUAL_TO, step_counter_2d)
    instruction_label = config.instruction_name.unique("While LoopCounter 2D < Step 2D")
    inner_sync_while_loop = outer_sync_while_loop.sync_sequence.add_sync_while(instruction_label, 90, sync_while_condition)

    # Add a sync block
    instruction_label = config.instruction_name.unique("Step voltage 2D")
    sync_block = inner_sync_while_loop.sync_sequence.add_sync_multi_sequence_block(instruction_label, 260)
    awg_sequence = sync_block.sequences[awg_engine_name]
    secondary_awg_sequence = sync_block.sequences[secondary_awg_engine_name]
    dig_sequence = sync_block.sequences[dig_engine_name]
    
    voltage_channel = sequencer.sync_sequence.scopes[secondary_awg_engine_name].registers[config.voltage_2d_name.format(config.AWG_channel_2d)]
    program_step_to_target_voltage(sequencer, secondary_awg_module, secondary_awg_sequence, config, config.AWG_channel_2d, voltage_channel, vf_2d, config.slew_rate_2d, use_dV_from_config = True, output_voltage=True)
    # If virtual gates are used, update the swept voltage on the other modules
    # If the 2D sweep is done with two AWG modules, update the voltage register on the other module used for sweeping
    if config.use_virtual_gates and config.main_awg_engine_name != secondary_awg_engine_name:
        voltage_channel = sequencer.sync_sequence.scopes[awg_module.engine_name].registers[config.vg_voltage_2d_name.format(config.AWG_channel_2d)]
        vg_awg_registers = sequencer.sync_sequence.scopes[awg_module.engine_name].registers
        vg_vf_2d = vg_awg_registers[config.vf_2d_name]
        program_step_to_target_voltage(sequencer, awg_module, awg_sequence, config, config.AWG_channel_2d, voltage_channel, vg_vf_2d, config.slew_rate_2d, use_dV_from_config=False, output_voltage=False, source_VG_module=secondary_awg_module)
    # Update the voltage register on the other modules
    for virtual_gate_module in virtual_gates_modules:
        voltage_channel = sequencer.sync_sequence.scopes[virtual_gate_module.engine_name].registers[config.vg_voltage_2d_name.format(config.AWG_channel_2d)]
        vg_awg_registers = sequencer.sync_sequence.scopes[virtual_gate_module.engine_name].registers
        vg_vf_2d = vg_awg_registers[config.vf_2d_name]
        program_step_to_target_voltage(sequencer, virtual_gate_module, sync_block.sequences[virtual_gate_module.engine_name], config, config.AWG_channel_2d, voltage_channel, vg_vf_2d, config.slew_rate_2d, use_dV_from_config=False, output_voltage=False, source_VG_module=secondary_awg_module)

    # Increment AWG loop counter
    instruction_label = config.instruction_name.unique("AWG loop counter 2D += 1")
    instruction = secondary_awg_sequence.add_instruction(instruction_label, 10, secondary_awg_sequence.instruction_set.add.id)
    instruction.set_parameter(secondary_awg_sequence.instruction_set.add.destination.id, awg_loop_counter_2d)
    instruction.set_parameter(secondary_awg_sequence.instruction_set.add.left_operand.id, awg_loop_counter_2d)
    instruction.set_parameter(secondary_awg_sequence.instruction_set.add.right_operand.id, 1)
    
    instruction_label = config.instruction_name.unique("Loop Counter 2D += 1")
    instruction = dig_sequence.add_instruction(instruction_label, 200, dig_sequence.instruction_set.add.id)
    instruction.set_parameter(dig_sequence.instruction_set.add.destination.id, loop_counter_2d)
    instruction.set_parameter(dig_sequence.instruction_set.add.left_operand.id, loop_counter_2d)
    instruction.set_parameter(dig_sequence.instruction_set.add.right_operand.id, 1)
    
    if config.use_virtual_gates and (awg_engine_name != secondary_awg_engine_name):
        sweeper_1d(outer_sync_while_loop, awg_module, dig_module, config, virtual_gates_modules=[secondary_awg_module]+virtual_gates_modules)
    else:
        sweeper_1d(outer_sync_while_loop, awg_module, dig_module, config, virtual_gates_modules=virtual_gates_modules)

    # Add a sync block
    instruction_label = config.instruction_name.unique("Reset AWG loop counter 2D")
    sync_block = sequencer.sync_sequence.add_sync_multi_sequence_block(instruction_label, 510)
    awg_sequence = sync_block.sequences[secondary_awg_engine_name]
    secondary_awg_sequence = sync_block.sequences[secondary_awg_engine_name]

    instruction_label = config.instruction_name.unique("AWG loop counter 2D = 0")
    instruction = secondary_awg_sequence.add_instruction(instruction_label, 10, secondary_awg_sequence.instruction_set.assign.id)
    instruction.set_parameter(secondary_awg_sequence.instruction_set.assign.destination.id, awg_loop_counter_2d)
    instruction.set_parameter(secondary_awg_sequence.instruction_set.assign.source.id, 0)

    # Stop emulator at the end of the sequence
    if config.use_QD_emulator and not config.hardware_simulated:
        writeMemoryMap = dig_sequence.add_instruction("Write reg_HLS_start = 0", 30, dig_sequence.instruction_set.fpga_array_write.id)
        fpga_memory_map_DIG = dig_sequence.engine.fpga_sandboxes[config.M3xxxA_sandbox].fpga_memory_maps[config.MemoryEngine_QD_emulator_name]
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map.id, fpga_memory_map_DIG)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.fpga_memory_map_offset.id, 0)
        writeMemoryMap.set_parameter(dig_sequence.instruction_set.fpga_array_write.value.id, 0)
    

def measure_data(config: ApplicationConfig2D, awg_module: Module, dig_module : Module, hvi: kthvi.Hvi, channel_list: list, max_time: float, timeout=1000, countdown=True, live_plotting=True, average_data=False, save_data=False, header="", savepath="default_Sweeper2D_datafile.txt", plot_pyqtgraph=False)-> np.ndarray:
    """
    Measure the data from the selected digitizer channel in the config.

    Parameters
    ----------
    config : ApplicationConfig2D class
        Experiment configuration.
    awg_module : Module object
        AWG module used for the measurement.
    dig_module : Module object
        Digitizer module used for the measurement.
    kthvi.Hvi object
        Compiled HVI sequence.
    channel_list : list
        List of digitizer channels to measure.
    max_time : int, optional
        Maximum time allowed between two data acquisition in seconds, by default 5.
    timeout : int, optional
        Maximum time allowed for the data acquisition in milliseconds, by default 1000.
    countdown : bool, optional
        Show measurement countdown in the console, by default True.
    live_plotting : bool, optional
        Choose whether to plot the data in real time or not, by default True.
    average_data : bool, optional
        Choose whether to average the points measured in a cycle or not, by default False.
    save_data : bool, optional
        Choose whether to save the data in a text file or not, by default False.
    header : str, optional
        Header of the text file where the data is saved, by default "".
    savepath : str, optional
        Path of the text file where the data is saved, by default "default_Sweeper2D_datafile.txt".
    plot_pyqtgraph : bool, optional
        Choose whether to plot the data using pyqtgraph or not, by default False. If False, matplotlib is used.

    Returns
    -------
    np.ndarray
        Data array from the digitizer channel.
    """
    awg_engine_name = awg_module.engine_name
    dig_engine_name = dig_module.engine_name

    # Append header with data array shape and column names
    header += "\nreadback numpy shape for line part: {}, {}\n".format(config.num_steps_2d, config.num_steps_1d)
    axes_list = ["Voltage 2D","Voltage 1D"]
    if not average_data:
        axes_list.append("Trace time")
    config.logger.debug("Measuring data on ch {}...".format(", ".join(str(ch_num) for ch_num in channel_list)))
    for ch in channel_list:
        axes_list.append("Digitizer Ch{}".format(ch))
    axes_list.append("time")
    header += "\t".join(axes_list)

    # Create channel mask in binary format
    channel_mask = 0x0000 # LSB is CH1, bit 1 is CH2 and so on
    for ch in channel_list:
        channel_mask |= 1 << (ch-1)

    # AWG registers
    awg_registers = hvi.sync_sequence.scopes[awg_engine_name].registers
    secondary_awg_registers = hvi.sync_sequence.scopes[config.secondary_awg_engine_name].registers
    voltage_channel_1d = awg_registers[config.voltage_1d_name.format(config.AWG_channel_1d)]
    voltage_channel_2d = secondary_awg_registers[config.voltage_2d_name.format(config.AWG_channel_2d)]
    vi_1d = awg_registers[config.vi_1d_name]
    vf_1d = awg_registers[config.vf_1d_name]
    vi_2d = secondary_awg_registers[config.vi_2d_name]
    vf_2d = secondary_awg_registers[config.vf_2d_name]
    # slew_time = awg_registers[config.slew_time_name]
    sweep_direction = awg_registers[config.sweep_direction_name]
    neg_counter = awg_registers[config.neg_counter_name]
    awg_loop_counter_1d = awg_registers[config.awg_loop_counter_1d_name]
    ramp_counter_1d = awg_registers[config.ramp_counter_1d_name]
    awg_loop_counter_2d = secondary_awg_registers[config.awg_loop_counter_2d_name]
    ramp_counter_2d = secondary_awg_registers[config.ramp_counter_2d_name]
    vg_voltage_1d = secondary_awg_registers[config.vg_voltage_1d_name.format(config.AWG_channel_1d)]
    vg_voltage_2d = awg_registers[config.vg_voltage_2d_name.format(config.AWG_channel_2d)]

    # awg_debug = awg_registers[config.awg_debug_name]

    # Dig registers
    dig_registers = hvi.sync_sequence.scopes[dig_engine_name].registers # digitizer registers collection
    loop_counter_1d = dig_registers[config.loop_counter_1d_name]
    dig_debug = dig_registers[config.dig_debug_name]
    step_counter_1d = dig_registers[config.step_counter_1d_name]
    hvi_done = dig_registers[config.hvi_done_name]
    num_cycles_seg = dig_registers[config.num_cycles_seg_name]
    num_cycles_since_config = dig_registers[config.num_cycles_since_config_name]

    # Read registers for debugging
    vi_1d_read = vi_1d.read()
    vf_1d_read = vf_1d.read()
    vi_2d_read = vi_2d.read()
    vf_2d_read = vf_2d.read()
    # slew_time_read = slew_time.read()
    sweep_direction_read = sweep_direction.read()
    neg_counter_read = neg_counter.read()
    # awg_debug_read = awg_debug.read()
    voltage_channel_1d_read = voltage_channel_1d.read()
    voltage_channel_2d_read = voltage_channel_2d.read()
    loop_counter_1d_read = loop_counter_1d.read()
    dig_debug_read = dig_debug.read()
    step_counter_1d_read = step_counter_1d.read()
    vg_voltage_1d_read = vg_voltage_1d.read()
    vg_voltage_2d_read = vg_voltage_2d.read()

    config.logger.debug("Vi 1D: {}".format(vi_1d_read))
    config.logger.debug("Vf 1D: {}".format(vf_1d_read))
    config.logger.debug("Vi 2D: {}".format(vi_2d_read))
    config.logger.debug("Vf 2D: {}".format(vf_2d_read))
    # config.logger.debug("Slew Time: {}".format(slew_time_read))
    config.logger.debug("Neg counter: {}".format(neg_counter_read))
    config.logger.debug("Init Voltage Ch{}: {}".format(config.AWG_channel_1d, voltage_channel_1d_read))
    config.logger.debug("Init Voltage Ch{}: {}".format(config.AWG_channel_2d, voltage_channel_2d_read))
    # config.logger.debug("AWG Debug: {}".format(awg_debug_read))
    config.logger.debug("Step counter: {}".format(step_counter_1d_read))
    config.logger.debug("Loop counter: {}".format(loop_counter_1d_read))
    config.logger.debug("DIG Debug: {}".format(dig_debug_read))
    config.logger.debug("VG Voltage 1D ({}): {}".format(config.secondary_awg_engine_name, vg_voltage_1d_read))
    config.logger.debug("VG Voltage 2D ({}): {}".format(config.main_awg_engine_name, vg_voltage_2d_read))

    if config.use_QD_emulator:
        conversion_factor = 2**-12
    else:
        conversion_factor = float(config.fullscale)/(2.**15 -1)
  
    # Initialize data array
    max_points = config.acquisition_points_per_cycle*config.num_cycles
    if average_data:
        buffer = []
        for i, ch in enumerate(channel_list):
            buffer.append(np.array([]))
        averaged_data = np.empty((len(channel_list), config.num_cycles))
        averaged_data[:] = np.nan

        averaged_data_index = [0]*len(channel_list) # first empty slot in the averaged_data array

        # Axis arrays to be saved in the text file as 1D arrays
        x_array = np.tile(np.linspace(config.vi_1d, config.vf_1d, config.num_steps_1d), config.num_steps_2d)
        y_array = np.repeat(np.linspace(config.vi_2d, config.vf_2d, config.num_steps_2d), config.num_steps_1d)
        time_array = np.empty(config.num_cycles)
        time_array[:] = np.nan
    else:
        measured_data = np.empty((len(channel_list), max_points))
        measured_data[:] = np.nan
        x_array = np.tile(np.repeat(np.linspace(config.vi_1d, config.vf_1d, config.num_steps_1d), config.acquisition_points_per_cycle), config.num_steps_2d)
        y_array = np.repeat(np.repeat(np.linspace(config.vi_2d, config.vf_2d, config.num_steps_2d), config.acquisition_points_per_cycle), config.num_steps_1d)
        trace_time_array = np.tile(np.linspace(0, config.integration_time, config.acquisition_points_per_cycle), config.num_cycles)
        time_array = np.empty(max_points)
        time_array[:] = np.nan

    old_readPoints = [0]*len(channel_list)
    readPoints = [0]*len(channel_list)
    data_all_read = [False]*len(channel_list)
    timeout_counter = [0]*len(channel_list)
    saved_data_index = 0
    start_time = time.time()
    t = 0
    log_interval = 0.3
    next_log = 0
    cycles_per_segment, num_segments = calc_num_cycles_per_segment(config.num_cycles, config.acquisition_points_per_cycle, config.use_QD_emulator)
    segments_measured = 0
    config.logger.info("Number of cycles: {}".format(config.num_cycles))
    config.logger.info("Cycles per segment: {}".format(cycles_per_segment))
    config.logger.info("Number of segments: {}".format(num_segments))

    # Define stop event and set to false even if not averaging
    stop_event = Event()
    stop_event.clear()

    if live_plotting and average_data:
        # Set data to plot
        graph_data = averaged_data[0]
        
        if plot_pyqtgraph and PYQTGRAPH_INSTALLED:
            # Interpret image data as row-major instead of col-major
            pqt.setConfigOptions(imageAxisOrder='row-major')

            pqt.mkQApp()
            win = QtWidgets.QWidget()
            graph_widget = pqt.GraphicsLayoutWidget()
            graph_widget.setWindowTitle('Sweeper 2D live plot')
            
            # A plot area (ViewBox + axes) for displaying the image
            p1 = graph_widget.addPlot(title="")

            # Item for displaying image data
            img = pqt.ImageItem()
            p1.addItem(img)
            p1.setLabel('bottom', 'X Axis Label')  # x-axis
            p1.setLabel('left', 'Y Axis Label')  # y-axis
            img.setImage(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)))
            img.setRect(QtCore.QRectF(config.vi_1d, config.vf_2d, config.vf_1d-config.vi_1d, config.vf_2d-config.vi_2d))

            # Contrast/color control
            hist = pqt.HistogramLUTItem()
            hist.setImageItem(img)
            graph_widget.addItem(hist)
            hist.setLevels(0, 1)

            # Create a grid layout to manage the widgets size and position
            layout = QtWidgets.QGridLayout()
            win.setLayout(layout)

            # Add widgets to the layout in their proper positions
            stop_button = QtWidgets.QPushButton('Stop')
            stop_button.clicked.connect(lambda: stop_event.set())
            layout.addWidget(stop_button, 0, 0)  # button goes in upper-left
            layout.addWidget(graph_widget, 0, 1, 3, 1)  # plot goes on right side, spanning 3 rows

            # Get the colormap from matplotlib  
            cmap = plt.get_cmap("bwr") # or viridis
            positions = np.array([0.0, 0.5, 1.0]) # Define the positions and get the corresponding colors
            colors = cmap(positions)
            colors_255 = (colors[:, :3] * 255).astype(np.uint8) # Convert to 8-bit RGB values
            pg_cmap = pqt.ColorMap(positions, colors_255) # Create the PyQTGraph colormap
            hist.gradient.setColorMap(pg_cmap) # Set the colormap
            
            graph_widget.resize(800, 800)
            win.show()

            # Start plotting
            app = QtWidgets.QApplication.instance()
        else:
            plt.figure("Live plot")
            plt.clf() # avoid multiple colorbar
            graph = plt.imshow(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)), extent=[config.vi_1d, config.vf_1d, config.vi_2d, config.vf_2d], aspect='auto', origin='lower')
            plt.xlabel("Voltage Ch{} [V]".format(config.AWG_channel_1d))
            plt.ylabel("Voltage Ch{} [V]".format(config.AWG_channel_2d))
            cbar = plt.colorbar()
            cbar.set_label("Signal", rotation=90)
            plt.draw()

            # Add stop button to the figure
            stop_event = Event()
            ax_stop = plt.axes([0.65, 0.95, 0.1, 0.04])
            button_stop = Button(ax_stop, 'Stop')
            def stop(event):
                hvi.stop()
                stop_event.set()
            button_stop.on_clicked(stop)

    # Prepare file to save data
    if save_data:
        with open(savepath, "w") as f:
            np.savetxt(f, np.array([]), header=header, comments="#") # comments="#" for compatibility with readfile from pyHegel
        
    for i, ch in enumerate(channel_list):
        config.logger.debug("{}/{} points read on ch{}".format(readPoints[i], max_points, ch))
    ready_pts = 0
    while (not all(data_all_read) or hvi_done.read() == 0) and not stop_event.is_set():
        t = time.time() - start_time

        if live_plotting and average_data:
            if plot_pyqtgraph and PYQTGRAPH_INSTALLED:
                img.setImage(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)))
                app.processEvents()
            else:
                graph.set_data(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)))
                # Update colorbar
                graph.set_clim(vmin=np.nanmin(graph_data), vmax=np.nanmax(graph_data))
                plt.draw()
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 20)

        if t > next_log:
            voltage_channel_1d_read = voltage_channel_1d.read()
            voltage_channel_2d_read = voltage_channel_2d.read()
            vg_voltage_1d_read = vg_voltage_1d.read()
            vg_voltage_2d_read = vg_voltage_2d.read()
            config.logger.debug("Voltage Ch{}: {}".format(config.AWG_channel_1d, voltage_channel_1d_read))
            config.logger.debug("Voltage Ch{}: {}".format(config.AWG_channel_2d, voltage_channel_2d_read))
            config.logger.debug("AWG loop counter 1D: {}/{}".format(awg_loop_counter_1d.read(), ramp_counter_1d.read()))
            config.logger.debug("AWG loop counter 2D: {}/{}".format(awg_loop_counter_2d.read(), ramp_counter_2d.read()))
            config.logger.debug("DIG loop counter: {}/{}".format(loop_counter_1d.read(), step_counter_1d.read()))
            config.logger.debug("DIG Debug: {}".format(dig_debug.read()))
            config.logger.debug("VG Voltage 1D ({}): {}".format(config.secondary_awg_engine_name, vg_voltage_1d_read))
            config.logger.debug("VG Voltage 2D ({}): {}".format(config.main_awg_engine_name, vg_voltage_2d_read))
            for i, ch in enumerate(channel_list):
                config.logger.debug("{}/{} points read on ch{}".format(readPoints[i], max_points, ch))
            config.logger.debug("Ready points: {:.02f}M pts".format(ready_pts/1e6))
            next_log = next_log + log_interval

            for i, ch in enumerate(channel_list):
                if readPoints[i] == old_readPoints[i] and readPoints[i] > 0: # Check for measurement timeout only after the measurement has started
                    timeout_counter[i] = timeout_counter[i] + 1
                    if timeout_counter[i] > round(max_time/log_interval):
                        config.logger.info("Timeout during measurement")
                        stop_event.set()
                old_readPoints[i] = readPoints[i]

        for i, ch in enumerate(channel_list):
            ready_pts = dig_module.instrument.DAQcounterRead(ch)
            if ready_pts > 0:
                timeout_counter = [0]*len(channel_list)
                data = dig_module.instrument.DAQread(ch, ready_pts, timeout) # return a Numpy array
                try:
                    if average_data:
                        # Add buffer before data
                        if buffer[i].size > 0:
                            data = np.append(buffer[i], data)
                            buffer[i] = np.array([])
                        if data.size >= config.acquisition_points_per_cycle:
                            # Find the number of points that fill the buffer and average them directly
                            nb_filled_buffers = data.size // config.acquisition_points_per_cycle
                            averaged_data[i][averaged_data_index[i]:averaged_data_index[i]+nb_filled_buffers] = np.mean(data[:nb_filled_buffers*config.acquisition_points_per_cycle].reshape((nb_filled_buffers, config.acquisition_points_per_cycle)), axis=1)*conversion_factor
                            
                            if i == 0:
                                time_array[averaged_data_index[i]:averaged_data_index[i]+nb_filled_buffers] = time.time()

                            averaged_data_index[i] = averaged_data_index[i] + nb_filled_buffers

                            # Move the remaining data to the buffer
                            buffer[i] = data[nb_filled_buffers*config.acquisition_points_per_cycle:]

                        else:
                            # Move data to buffer
                            buffer[i] = data

                    else:
                        measured_data[i][readPoints[i]:readPoints[i]+ready_pts] = data*conversion_factor
                        if i == 0:
                            time_array[readPoints[i]:readPoints[i]+ready_pts] = time.time()

                except:
                    config.logger.debug("Was expecting {} pts and measured {}.".format(ready_pts, len(data)))
                    raise
                readPoints[i] = readPoints[i] + ready_pts
                # Reset old_readPoints if measurement is complete to avoid timeout
                if readPoints[i] == max_points:
                    old_readPoints[i] = 0

                progress_string = "Progress: "
                if countdown:
                    for i, ch in enumerate(channel_list):
                        progress_string = progress_string + "ch{}={}%|".format(ch, round(readPoints[i]/max_points*100)) 
                    progress_string = progress_string[:-1] # remove last "|"
                    print(progress_string, end='\r')

            else:
                # Check if a complete segment of data has been measured
                num_cycles_seg_read = num_cycles_seg.read()
                num_cycles_since_config_read = num_cycles_since_config.read()
                if num_cycles_since_config_read >= num_cycles_seg_read:
                    config.logger.debug("Number of cycles since config / in segment: {} / {}".format(num_cycles_since_config_read, num_cycles_seg_read))
                    segments_measured = segments_measured + 1
                    config.logger.debug("Segment {} of {} measured.".format(segments_measured, num_segments))
                    if segments_measured == num_segments:
                        config.logger.debug("All segments measured. Not configuring the digitizer for the next segment.")
                        pass # Do nothing if the last segment is already measured
                    elif segments_measured == num_segments - 1: # if we are measuring the second last segment
                        # Calculate the number of cycles for the last segment
                        remaining_cycles = config.num_cycles - cycles_per_segment*(num_segments - 1)
                        config.logger.debug("Configuring the digitizer for the last segment of {} cycles.".format(remaining_cycles))
                        configure_digitizer(config, dig_module, num_cycles_override=remaining_cycles)
                    else:
                        config.logger.debug("Configuring the digitizer for the next full segment of {} cycles.".format(cycles_per_segment))
                        configure_digitizer(config, dig_module)

                    # Reset the number of cycles read since config
                    num_cycles_since_config.write(0)
                    config.logger.debug("Resetting 'Num cycles since config' register to 0.")

            if readPoints[i] >= max_points:
                data_all_read[i] = True

        if save_data:
            if average_data:
                array_to_save = averaged_data
            else:
                array_to_save = measured_data

            for i, ch in enumerate(channel_list):
                if i == 0:
                    smallest_array_size = np.count_nonzero(~np.isnan(array_to_save[i]))
                else:
                    smallest_array_size = min(smallest_array_size, np.count_nonzero(~np.isnan(array_to_save[i])))
        
            if average_data:
                with open(savepath, "a") as f:
                    np.savetxt(f, np.vstack((y_array[saved_data_index:smallest_array_size], x_array[saved_data_index:smallest_array_size], array_to_save[:, saved_data_index:smallest_array_size], time_array[saved_data_index:smallest_array_size])).T, comments="#") # comments="#" for compatibility with readfile from pyHegel
            else:
                with open(savepath, "a") as f:
                    np.savetxt(f, np.vstack((y_array[saved_data_index:smallest_array_size], x_array[saved_data_index:smallest_array_size], trace_time_array[saved_data_index:smallest_array_size], array_to_save[:, saved_data_index:smallest_array_size], time_array[saved_data_index:smallest_array_size])).T, comments="#")

            saved_data_index = smallest_array_size

    if countdown: print("")
    config.logger.debug("Voltage Ch{}: {}".format(config.AWG_channel_1d, voltage_channel_1d_read))
    config.logger.debug("Voltage Ch{}: {}".format(config.AWG_channel_2d, voltage_channel_2d_read))
    config.logger.debug("AWG loop counter 1D: {}/{}".format(awg_loop_counter_1d.read(), ramp_counter_1d.read()))
    config.logger.debug("AWG loop counter 2D: {}/{}".format(awg_loop_counter_2d.read(), ramp_counter_2d.read()))
    config.logger.debug("DIG loop counter: {}/{}".format(loop_counter_1d.read(), step_counter_1d.read()))
    config.logger.debug("DIG Debug: {}".format(dig_debug.read()))
    for i, ch in enumerate(channel_list):
        config.logger.debug("{}/{} points read on ch{}".format(readPoints[i], max_points, ch))


    if stop_event.is_set():
        config.logger.info("HVI execution stopped...")
    elif hvi_done.read() == 1:
        config.logger.info("HVI execution completed successfully!")
    else:
        config.logger.info("HVI execution not completed...")

    for i, ch in enumerate(channel_list):
        if readPoints[i] < config.acquisition_points:
            config.logger.warning("MISSING DATA! Measured only {}/{} points.".format(readPoints[i], config.acquisition_points))

        # Save NaNs for the missing points to preserve the data array's dimensions
        if average_data:
            array_to_save = averaged_data[saved_data_index:]
        else:
            array_to_save = measured_data[saved_data_index:]
        with open(savepath, "a") as f:
            np.savetxt(f, array_to_save.T, comments="#") # comments="#" for compatibility with readfile from pyHegel

    if live_plotting and average_data:
        if plot_pyqtgraph and PYQTGRAPH_INSTALLED:
            img.setImage(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)))
            app.processEvents()
        else:
            # Final live plot update
            graph.set_data(graph_data.reshape((config.num_steps_2d, config.num_steps_1d)))
            # Update colorbar
            graph.set_clim(vmin=np.nanmin(graph_data), vmax=np.nanmax(graph_data))
            plt.draw()
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 20)

        config.logger.info("Measurement done in {:.04f}s".format(t))

    if average_data:
        if plot_pyqtgraph and PYQTGRAPH_INSTALLED:
            config.win = win # save the object to keep the window open
        else:
            config.win = None
        return averaged_data
    else:
        return measured_data

#%%
# Main Program
######################################
    
def prepare_hvi_sequence(sequencer: kthvi.Sequencer, config: ApplicationConfig2D, awg_module: Module, dig_module: Module, secondary_awg_module: Module, export_sequence=False, virtual_gates_modules=[])-> kthvi.Hvi:
    """
    Prepare and compile the HVI sequence for the 2D sweeper. The sequence is then sent to the modules.

    Parameters
    ----------
    sequencer : kthvi.Sequencer object
        HVI sequence definition.
    config : ApplicationConfig2D class
        Experiment configuration.
    awg_module : Module object
        AWG module used for the measurement.
    dig_module : Module object
        Digitizer module used for the measurement.
    secondary_awg_module : Module object
        Secondary AWG module used for the 2D sweep.
    export_sequence : bool, optional
        Export the HVI to a text file, by default False.
    virtual_gates_modules : list of Module objects, optional
        List of modules used for the virtual gates excluding the awg_module and secondary_awg_module, by default [].

    Returns
    -------
    kthvi.Hvi object
        Compiled HVI sequence.
    """
    # Define registers within the scope of the outmost sync sequence
    define_awg_registers_1d(sequencer, awg_module, config)
    define_dig_registers_1d(sequencer, dig_module, config)

    define_awg_registers_2d(sequencer, awg_module, config)
    define_dig_registers_2d(sequencer, dig_module, config)

    instruction_label = config.instruction_name.unique("Initialize registers")
    sync_block = sequencer.sync_sequence.add_sync_multi_sequence_block(instruction_label, 30)
    initialize_awg_registers_1d(sync_block, awg_module, config)
    initialize_dig_registers_1d(sync_block, dig_module, config)

    if secondary_awg_module.engine_name != awg_module.engine_name:
        define_awg_registers_1d(sequencer, secondary_awg_module, config)
        define_awg_registers_2d(sequencer, secondary_awg_module, config) 
        initialize_awg_registers_2d(sync_block, secondary_awg_module, config)
    else:
        initialize_awg_registers_2d(sync_block, awg_module, config)

    for module in virtual_gates_modules:
        # Registers are initialized in the update_vg_registers function
        define_awg_registers_1d(sequencer, module, config)
        define_awg_registers_2d(sequencer, module, config) 

    sweeper_2d(sequencer, config, awg_module, dig_module, secondary_awg_module, virtual_gates_modules=virtual_gates_modules)
    set_hvi_done(sequencer, dig_module, config)

    if export_sequence:
        # Export the programmed sequence to text
        export_hvi_sequences(sequencer, os.path.join(os.path.dirname(os.path.realpath(__file__)), r".\Sweeper2D_KS2201A.txt"))

    # Compile HVI sequences
    try:
        config.logger.info("Compiling HVI sequence...")
        hvi = sequencer.compile()
        config.logger.info('Compilation completed successfully!')
    except kthvi.CompilationFailed as err:
        config.logger.exception('Compilation failed!')
        raise

    config.logger.info("This HVI needs to reserve {} PXI trigger resources to execute".format(len(hvi.compile_status.sync_resources)))

    # Load HVI to HW: load sequences, configure actions/triggers/events, lock resources, etc.
    hvi.load_to_hw()
    config.logger.info("HVI Loaded to HW")

    return hvi

def run_hvi(config: ApplicationConfig2D, awg_module: Module, dig_module: Module, hvi: kthvi.Hvi, channel_list: list, max_time: float, countdown=True, live_plotting=True, average_data = False, save_data=False, header="", savepath="default_Sweeper2D_datafile.txt", plot_pyqtgraph=False)-> np.ndarray:
    """
    Run the compiled HVI sequence and return the data. One or four arrays are returned depending if all channels are measured or not.

    Parameters
    ----------
    config : ApplicationConfig2D class
        Experiment configuration.
    awg_module : Module object
        AWG module used for the measurement.
    dig_module : Module object
        Digitizer module used for the measurement.
    hvi : kthvi.Hvi object
        Compiled HVI sequence.
    channel_list : list
        List of channels to measure.
    max_time : int, optional
        Maximum time allowed between two data acquisition in seconds, by default 5.
    measure_all_ch : bool, optional
        Measure only one channel or all four channels from the digitizer, by default False.
    countdown : bool, optional
        Show measurement countdown in the console, by default True.
    live_plotting : bool, optional
        Choose whether to plot the data live or not, by default True. Option only available when measure_all_ch is False.
    average_data : bool, optional
        Choose whether to average the points measured in a cycle or not, by default False. Option only available when measure_all_ch is False.
    save_data : bool, optional
        Choose whether to save the data in a text file or not, by default False.
    header : str, optional
        Header of the text file where the data is saved, by default "".
    savepath : str, optional
        Directory where the data is saved, by default "default_Sweeper2D_datafile.txt".
    plot_pyqtgraph : bool, optional
        Choose whether to plot the data with pyqtgraph or not, by default False. If False, the data is plotted with matplotlib.

    Returns
    -------
    One or four np.ndarray
        Data array or arrays from the experiment.
    """
    # Execute HVI in non-blocking mode
    # This mode allows SW execution to interact with HVI execution
    config.logger.info("HVI Running...")
    hvi.run(hvi.no_wait)

    try:
        if not config.hardware_simulated:
            data = measure_data(config, awg_module, dig_module, hvi, channel_list=channel_list, max_time=max_time, countdown=countdown, live_plotting=live_plotting, average_data=average_data, save_data=save_data, header=header, savepath=savepath, plot_pyqtgraph=plot_pyqtgraph)
        else:
            data =  np.array([])
            
        # Stopping the HVI program
        hvi.stop()
        config.logger.info("HVI stopped")

        return data

    except Exception as error:
        config.logger.exception(error)

        # Stopping the HVI program
        hvi.stop()
        config.logger.info("HVI stopped")

        # Release HW resources once HVI execution is completed
        hvi.release_hw()
        config.logger.info("Releasing HW...")

def prepare_first_diagram(config, module_dict: dict, awg_module: Module, dig_module: Module, secondary_awg_module: Module, virtual_gates_modules=[], export_sequence=True)-> kthvi.Hvi:
    """
    Prepare and compile the HVI sequence.

    Parameters
    ----------
    config : ApplicationConfigPnF class
        Experiment configuration.
    module_dict : dict
        Dictionary of the opened modules.
    awg_module : Module object
        AWG module used for the measurement.
    secondary_awg_module : Module object
        Secondary AWG module used for the 2D sweep.
    dig_module : Module object
        Digitizer module used for the measurement.
    virtual_gates_modules : list of Module objects, optional
        List of modules used for the virtual gates excluding the awg_module and secondary_awg_module, by default [].
    export_sequence : bool, optional
        Export the HVI sequence to a text file, by default True.

    Returns
    -------
    kthvi.Hvi object
        Compiled HVI sequence.
    """
    
    config.logger.info("Defining system...")
    sequencer = define_system(config, module_dict)
    config.logger.info("Sequencer ready.")
    hvi = prepare_hvi_sequence(sequencer, config, awg_module, dig_module, secondary_awg_module, export_sequence=export_sequence, virtual_gates_modules=virtual_gates_modules)
    
    return hvi
  
def measure_diagram(config: ApplicationConfig2D, module_dict: dict, hvi: kthvi.Hvi, channel_list, max_time=20, countdown=True, live_plotting=True, average_data=False, nb_averaging=1, save_data=False, header="", plot_pyqtgraph=False)-> np.ndarray:
    """
    Update the registers of the compiled HVI sequence and configure the modules before launching the next measurement.

    Parameters
    ----------
    config : ApplicationConfigPnF class
        Experiment configuration.
    module_dict : dict
        Dictionary of the opened modules.
    hvi : kthvi.Hvi object
        Compiled HVI sequence.
    channel_list : list
        List of channels to measure, by default channel_list.
    show_figure : bool, optional
        Parameter to show the figure or not, by default True.
    max_time : int, optional
        Maximum time allowed between two data acquisition in seconds, by default 20.
    countdown : bool, optional
        Prints a countdown during the experiment, by default True.
    live_plotting : bool, optional
        Choose whether to plot the data live or not, by default True.
    average_data : bool, optional
        Choose whether to average the points measured in a cycle or not, by default False.
    nb_averaging : int, optional
        Number of times the measurement is repeated and averaged, by default 1. Option only available when measure_all_ch is False.
    save_data : bool, optional
        Choose whether to save the data in a text file or not, by default False.
    header : str, optional
        Header of the text file where the data is saved, by default "".
    plot_pyqtgraph : bool, optional
        Choose whether to plot the data with pyqtgraph or not, by default False. If False, the data is plotted with matplotlib.

    Returns
    -------
    1D np.ndarray
        Data of the stability diagram
    """
    # Get database_folder and save_filename from config
    database_folder = config.database_folder
    save_filename = config.save_filename
    day_folder, filename_incr = create_save_filename(database_folder, save_filename)
    savepath = os.path.join(day_folder, filename_incr)
    yaml_config_filename = "{}_config.yaml".format(filename_incr[:-4])
    config_savepath = os.path.join(day_folder, yaml_config_filename)

    src_dir = config.yaml_file
    shutil.copy(src_dir, config_savepath)

    awg_module = module_dict[config.main_awg_engine_name]
    dig_module = module_dict[config.main_dig_engine_name]
    secondary_awg_module = module_dict[config.secondary_awg_engine_name]

    # Prepare awg module dict
    awg_module_dict = module_dict.copy()
    for engine_name in list(awg_module_dict.keys()):
        module = awg_module_dict[engine_name]
        if isinstance(module.instrument, keysightSD1.SD_AIN):
            awg_module_dict.pop(engine_name)

    update_awg_registers_1d(hvi, awg_module, config, module_dict)
    update_dig_registers_1d(hvi, dig_module, config)
    update_awg_registers_2d(hvi, secondary_awg_module, config, module_dict)
    update_dig_registers_2d(hvi, dig_module, config)

    if average_data and nb_averaging > 1 and live_plotting:
        averaging_index = 0
        measurement_sum = np.zeros(config.num_cycles)
        fig = plt.figure(num="Live averaging") 
        subfig, ax = plt.subplots(num=fig.number)  # Create a figure and an axes.
        graph = ax.imshow(measurement_sum.reshape((config.num_steps_2d, config.num_steps_1d)), extent=[config.vi_1d, config.vf_1d, config.vi_2d, config.vf_2d], aspect='auto', origin='lower')
        ax.set_xlabel("Voltage Ch{} [V]".format(config.AWG_channel_1d))
        ax.set_ylabel("Voltage Ch{} [V]".format(config.AWG_channel_2d))
        cbar = subfig.colorbar(graph)
        cbar.set_label("Signal", rotation=90)
        ax.set_title("Average #{}".format(averaging_index))
        original_savepath = savepath

    for i in range(nb_averaging):
        if average_data and nb_averaging > 1:
            if plot_pyqtgraph: raise NotImplementedError("Live plotting with averaging is not implemented with pyqtgraph")
            # Insert average number before file extension in savepath
            savepath = original_savepath[:-4] + "_avg{}".format(i+1) + original_savepath[-4:]

        # Configure modules
        configure_digitizer(config, dig_module)
        for engine_name, module in awg_module_dict.items():
            configure_awg(config, module)
    
        data = run_hvi(config, awg_module, dig_module, hvi, channel_list=channel_list, max_time=max_time, countdown=countdown, live_plotting=live_plotting, average_data=average_data, save_data=save_data, header=header, savepath=savepath, plot_pyqtgraph=plot_pyqtgraph)
        if average_data:
            nb_points = config.num_cycles
        else:
            nb_points = config.num_cycles*config.acquisition_points_per_cycle
        
        redo_measurement = False
        for i, ch in enumerate(channel_list):
            true_len = len(data[i][~np.isnan(data[i])])
            if true_len < nb_points:
                redo_measurement = True
                config.logger.info("Measured only {}/{} points for ch{}. Restarting previous measurement because of timeout.".format(true_len, nb_points, ch))
        
        if redo_measurement:
            update_awg_registers_1d(hvi, awg_module, config, module_dict)
            update_dig_registers_1d(hvi, dig_module, config)
            update_awg_registers_2d(hvi, secondary_awg_module, config, module_dict)
            update_dig_registers_2d(hvi, dig_module, config)

            # Configure modules
            configure_digitizer(config, dig_module)
            for engine_name, module in awg_module_dict.items():
                configure_awg(config, module)

            data = run_hvi(config, awg_module, dig_module, hvi, channel_list=channel_list, max_time=max_time, countdown=countdown, live_plotting=live_plotting, average_data=average_data, save_data=save_data, header=header, savepath="{}_timeout.txt".format(savepath[:-4]), plot_pyqtgraph=plot_pyqtgraph)
    
        if average_data and nb_averaging > 1 and live_plotting:
            plt.figure("Live averaging")
            averaging_index += 1
            ax.set_title("Average #{}".format(averaging_index))
            measurement_sum = measurement_sum + data
            averaged_measurement = measurement_sum/averaging_index
            graph.set_data(averaged_measurement.reshape((config.num_steps_2d, config.num_steps_1d)))
            # Update colorbar
            graph.set_clim(vmin=np.nanmin(averaged_measurement), vmax=np.nanmax(averaged_measurement))
            plt.draw()
            plt.pause(0.01)  # Add a short pause to allow the plot to update

    if average_data and nb_averaging > 1 and save_data:
        with open(original_savepath, "w") as f:
            header = header + "\nAveraged over {} measurements".format(nb_averaging)
            np.savetxt(f, averaged_measurement, header=header, comments="#") # comments="#" for compatibility with readfile from pyHegel


    return data

def plot_diagram(config: ApplicationConfig2D, data: np.ndarray, channel_list: list, is_averaged=False):
    """
    Plot the stability diagram.

    Parameters
    ----------
    config : ApplicationConfigPnF class
        Experiment configuration.
    data : 1D np.ndarray
        Data of the stability diagram
    channel_list : list
        List of channels to measure.
    is_averaged : bool, optional
        Specify if the data is averaged or not, by default False.
    """

    for i, ch in enumerate(channel_list):
        graph_data = data[i]
        if is_averaged == False:
            averaged_data = graph_data.reshape((config.num_cycles, config.acquisition_points_per_cycle))
            averaged_data = np.mean(averaged_data, axis=1)
        else:
            averaged_data = graph_data

        reshaped_data = averaged_data.reshape((config.num_steps_2d, config.num_steps_1d))
        x = np.linspace(config.vi_1d, config.vf_1d, config.num_steps_1d)
        y = np.linspace(config.vi_2d, config.vf_2d, config.num_steps_2d)
        xv, yv = np.meshgrid(x, y)

        # Plot 2D data
        plt.figure()
        plt.pcolormesh(xv,yv,reshaped_data,cmap="viridis",shading="auto")
        plt.xlabel("Vg1 (V)")
        plt.ylabel("Vg2 (V)")
        cbar = plt.colorbar()
        cbar.set_label("Nb of electrons", rotation=90)
        plt.title("Digitizer channel {}".format(ch))
        plt.draw()


def run_experiment(countdown=True, plot_pyqtgraph=False):
    """
    Code example to measure multiple stability diagrams. Axes should be above 30 mV to avoid visualization issue.

    Parameters
    ----------
    countdown : bool, optional
        Prints a countdown during the experiment, by default True.
    plot_pyqtgraph : bool, optional
        Choose whether to plot the data with pyqtgraph or not, by default False. If false, the data is plotted with matplotlib.

    Returns
    -------
    win : pyqtgraph.Qt.QtWidgets.QtWidget
        Window containing the pyqtgraph plot if pyqtgraph is used. Saved in the config object. If pyqtgraph is not used, the variable is None.
    """

    try:
        # Load configuration file
        config = ApplicationConfig2D.from_yaml(os.path.join(os.path.dirname(__file__), "experiment_config_Sweeper2D.yaml"))

        # Open modules and load bitstreams
        # Returns a dictionary of module objects whose keys are the HVI engine names
        module_dict = open_modules(config)
        awg_module = module_dict[config.main_awg_engine_name]
        if config.secondary_awg_engine_name != config.main_awg_engine_name:
            secondary_awg_module = module_dict[config.secondary_awg_engine_name]
        else:
            secondary_awg_module = module_dict[config.main_awg_engine_name]

        virtual_gates_modules = []
        if config.third_awg_engine_name != None:
            third_awg_module = module_dict[config.third_awg_engine_name]
            virtual_gates_modules.append(third_awg_module)
        if config.fourth_awg_engine_name != None:
            fourth_awg_module = module_dict[config.fourth_awg_engine_name]
            virtual_gates_modules.append(fourth_awg_module)

        # Prepare awg module dict
        awg_module_dict = module_dict.copy()
        for engine_name in list(awg_module_dict.keys()):
            module = awg_module_dict[engine_name]
            if isinstance(module.instrument, keysightSD1.SD_AIN):
                awg_module_dict.pop(engine_name)

        config.logger.info("len(virtual_gates_modules): {}".format(len(virtual_gates_modules)))

        for engine_name, module in module_dict.items():
            if "AWG" in engine_name:
                load_awg(config, module, reset_voltages=False)

        dig_module = module_dict[config.main_dig_engine_name]
        load_digitizer(config, dig_module)

        hvi = prepare_first_diagram(config, module_dict, awg_module, dig_module, secondary_awg_module, virtual_gates_modules, export_sequence=True)

        if config.use_virtual_gates:
            # Set all voltages to zero
            for engine_name, module in awg_module_dict.items():
                set_voltages_to_zero(config, module)
            update_vg_registers(config, module_dict, hvi)

            # Send identity matrix to AWG 
            # config.logger.info("Sending identity matrix to FPGA.")
            # CC_matrix = np.identity(4*config.nb_VG_awg_modules)
            # send_CC_matrix(config, module_dict, hvi, CC_matrix)

            # Send DQD cross-capacitance matrix to AWG
            DQD_CC_matrix = np.array([
                                    [1, 0, 0, 0, 0, -0.1, 0, 0],
                                    [0, 1, 0, 0, 0, 0, 0, 0],
                                    [0, 0, 1, 0, 0, 0, 0, 0],
                                    [0, 0, 0, 1, 0, 0, 0, 0],
                                    [0, 0, 0, 0, 1, 0, 0, 0],
                                    [-0.1, 0, 0, 0, 0, 1, 0, 0],
                                    [0, 0, 0, 0, 0, 0, 1, 0],
                                    [0, 0, 0, 0, 0, 0, 0, 1]
                                    ])
            config.logger.info("Sending DQD matrix to FPGA.")
            send_CC_matrix(config, module_dict, hvi, DQD_CC_matrix)

        if config.use_virtual_gates:
            update_vg_registers(config, module_dict, hvi)

        average = True
        channel_list=[1]
        data = measure_diagram(config, module_dict, hvi, channel_list, max_time=config.max_time, countdown=countdown, live_plotting=True, average_data=average, save_data=True, header="test"+"\nshape=({},{})".format(config.num_steps_2d, config.num_steps_1d), plot_pyqtgraph=plot_pyqtgraph)
        plot_diagram(config, data, channel_list, is_averaged=average)

        if config.hardware_simulated:
            config.logger.info("Simulation completed successfully")
        else:
            # Tests with multiple successive diagrams
            for i in range(1,2):
                # Set experiment config
                config.logger.info("Iteration {}".format(i))

                config.vi_1d = 0+0.1*(i-1)
                config.vf_1d = 1+0.1*(i-1)
                config.vi_2d = 0+0.1*(i-1)
                config.vf_2d = 1+0.1*(i-1)
                if config.use_virtual_gates: update_vg_registers(config, module_dict, hvi)
                average = True
                data = measure_diagram(config, module_dict, hvi, channel_list, max_time=config.max_time, countdown=countdown, live_plotting=True, average_data=average, save_data=True, header="test"+"\nshape=({},{})".format(config.num_steps_2d, config.num_steps_1d), plot_pyqtgraph=plot_pyqtgraph)
                plot_diagram(config, data, channel_list, is_averaged=average)

            # Save data if needed
            # save_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Logs", "Sweeper2D", "QD_diagram_VG")
            # np.savez_compressed(save_dir, data=reshaped_data, header="V 1D: {},{},{}\nV 2D: {},{},{}\nCm: {}".format(config.vi_1d, config.vf_1d, config.num_steps_1d, config.vi_2d, config.vf_2d, config.num_steps_2d, config.QD_emulator_Cm))
        
        return config.win

    except Exception as error:
        config.logger.exception(error)
        # not raising, but the code stops after the finally block and the main block are executed

    finally:
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

if __name__ == "__main__":
    plt.ion()
    win = run_experiment(plot_pyqtgraph=False)
    plt.show(block=True)
else:
    logger = logging.getLogger(__name__)