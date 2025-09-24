import os
import sys
sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1
try:
    import keysight_tse as kthvi
except ImportError:
    import keysight_hvi as kthvi
import warnings
import yaml

class Firmware():
    def __init__(self, name, model, fw_version, uuid, path, nb_fpga_registers=0, description=""):
        """_summary_

        Parameters
        ----------
        name : string
            Name of the firmware. It should be the same for all firmwares that have the same function.
            For example, virtual gates can be used with many AWG models, so the different firmware should have the same name.
            However, the default firmwares for an AWG and a digitizer should have different names.
        model : string
            Model of the instrument (e.g. M3100A, M3202A, etc.)
        fw_version : string
            Firmware version of the instrument (found in the hardware manager of SD1).
        uuid : string
            Universally unique identifier of the firmware. 
            When the firmware is installed, use SD_Module.FPGAGetSandBoxKernelUUID() to get the UUID.
        path : string
            Path of the firmware file.
        nb_fpga_registers : int, optional
            Number of FPGA registers in the firmware. The default is 0 if the information isn't specified.
        description : string, optional
            Description of the firmware's functionalities. The default is "".
        """
        self.name = name
        self.model = model
        self.fw_version = fw_version
        self.uuid = uuid
        self.path = path
        self.nb_fpga_registers = nb_fpga_registers
        self.description = description

class FirmwareVersionTracker():
    def __init__(self):
        self.model_dict = {} # structure: {model}{name}[(fw_version, Firmware)]
        self.fw_database = [] # list containing all the firmwares

    def __str__(self):
        output = []
        for model, name_dict in self.model_dict.items():
            for name, version_list in name_dict.items():
                versions, fw = list(zip(*version_list))
                versions = list(versions)
                output.append("{} ({}): {}\n".format(name, model, versions))

        output = sorted(output, key=lambda v: v.upper())
        output[-1] = output[-1].rstrip("\n")
        return "".join(output)

    def add_new_fw(self, Firmware):
        name = Firmware.name
        model = Firmware.model
        fw_version = Firmware.fw_version
        uuid = Firmware.uuid
        path = Firmware.path
        nb_fpga_registers = Firmware.nb_fpga_registers
        description = Firmware.description

        # check if the firmware is already in the database
        for name_, model_, fw_version_, uuid_, path_, nb_fpga_registers_, description_ in self.fw_database:
            if name == name_ and model == model_ and fw_version == fw_version_ and uuid == uuid_ and path == path_:
                warnings.warn("Firmware already in database: {}".format(name))
                return

        # add to the text database
        self.fw_database.append([name, description, model, fw_version, uuid, path, nb_fpga_registers])

        # add to the class
        if model not in self.model_dict:
            self.model_dict[model] = {name: [(fw_version, Firmware)]}
        elif name not in self.model_dict[model]:
            self.model_dict[model][name] = [(fw_version, Firmware)]
        else:
            version_list = self.model_dict[model][name]
            version_list.append((fw_version, Firmware))
            self.model_dict[model][name] = sorted(version_list)

    def save_database(self, save_name="firmware_database.yaml", check_overwrite=True):
        save_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), save_name)
        yaml_database = {}

        for name_, description_, model_, fw_version_, uuid_, path_, nb_fpga_registers_ in self.fw_database:
            if name_ not in yaml_database:
                yaml_database[name_] = [{'description': description_}]

            yaml_database[name_].append({
                'model_number': model_,
                'firmware_version': fw_version_,
                'firmware_uuid': uuid_,
                'firmware_path': path_,
                'nb_registers': nb_fpga_registers_})

        yaml_str = yaml.dump({'firmware_database': yaml_database}, indent=2, sort_keys=False)
        
        # Split the YAML string by lines
        yaml_lines = yaml_str.split('\n')
        
        # Insert an empty line after each firmware name
        new_yaml_lines = []
        for i, line in enumerate(yaml_lines):
            if i == 0:
                continue
            else:
                previous_line = yaml_lines[i-1]
                if "nb_registers" in previous_line and "firmware_uuid" not in line:
                    new_yaml_lines.append('')

            new_yaml_lines.append(line)
    
        # Join the lines back into a single string
        formatted_yaml_str = '\n'.join(new_yaml_lines)

        if check_overwrite:
            # Save the YAML output to a file
            if os.path.exists(save_dir):
                user_input = input("The file {} already exists. Do you want to overwrite it? (y/n)".format(save_dir))
        else:
            user_input = "y"
    
        if user_input.lower() == "y" or user_input.lower() == "yes":
            with open(save_dir, 'w') as file:
                file.seek(0)
                file.write(formatted_yaml_str)
    
        return formatted_yaml_str


    def load_database(self, yaml_file="firmware_database.yaml"):
        load_dir=os.path.join(os.path.dirname(os.path.realpath(__file__)), yaml_file)
        with open(load_dir, 'r') as file:
            data = yaml.safe_load(file)

            for firmware_name, firmware_version_list in data.items():
                description = firmware_version_list[0]['description'] # list starts with the description
                for firmware in firmware_version_list[1:]:
                    model = firmware['model_number']
                    fw_version = firmware['firmware_version']
                    uuid = firmware['firmware_uuid']
                    path = firmware['firmware_path']
                    nb_fpga_registers = firmware['nb_registers']
                    self.add_new_fw(Firmware(firmware_name, model, fw_version, uuid, path, nb_fpga_registers, description))


    def get_fw(self, name, model, fw_version):
        fw_list = self.model_dict[model][name]
        for version, firmware in fw_list:
            if version == fw_version:
                return firmware

        # if the firmware is not found, raise the error
        versions, fw = list(zip(*fw_list))
        versions = list(versions) # convert tuple to list
        error_msg = "The firmware {} doesn't have a {} version.\n".format(name, fw_version)
        error_msg += "Available firmware versions are: {}\n".format(versions)
        error_msg += "Please recompile the project to get a {} version.".format(fw_version)
        raise ValueError(error_msg)

    def search_uuid(self, uuid):
        print("Searching for UUID {}...".format(repr(uuid)))
        for model, name_dict in self.model_dict.items():
            for name, version_list in name_dict.items():
                versions, firmwares = list(zip(*version_list))
                firmwares = list(firmwares)
                for fw in firmwares:
                    if uuid == fw.uuid:
                        print("UUID found: {} has UUID {}".format(fw.name, fw.uuid))
                        return fw

        print("UUID not found: {}".format(repr(uuid)))

    def check_module_firmware(self, model, chassis, slot):
        if model in ("M3100A", "M3102A"):
            module = keysightSD1.SD_AIN()
        else:
            module = keysightSD1.SD_AOU()

        try:
            print("Opening {} module in slot {} and chassis {} to check firmware version".format(model, slot, chassis))

            moduleID = module.openWithSlot(model, chassis, slot)
            if moduleID < 0: raise ValueError("Module open error: {}".format(keysightSD1.SD_Error.getErrorMessage(moduleID)))

            module_uuid = module.FPGAGetSandBoxKernelUUID()
            if isinstance(module_uuid, int) and module_uuid < 0: raise ValueError("FPGAGetSandBoxKernelUUID error: {}, {}".format(module_uuid, keysightSD1.SD_Error.getErrorMessage(module_uuid)))
            module_uuid = module_uuid.strip("\x00")
            firmware_library.search_uuid(module_uuid)

        finally:
            module.close()
            print("{} module in slot {} and chassis {} closed after firmware check".format(model, slot, chassis))

    def get_module_firmware_version(self, model, chassis, slot):
        if model in ("M3100A", "M3102A"):
            module = keysightSD1.SD_AIN()
        else:
            module = keysightSD1.SD_AOU()

        try:
            print("Opening module to check module info")

            moduleID = module.openWithSlot(model, chassis, slot)
            if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

            fw_version = module.getFirmwareVersion()
            if isinstance(fw_version, int) and fw_version < 0: raise ValueError("getFirmwareVersion error {}: {}".format(fw_version, keysightSD1.SD_Error.getErrorMessage(fw_version)))
            print(fw_version)

        finally:
            module.close()
            print("Module closed after module info is obtained")

def get_uuid_from_k7z(k7z_file, model, chassis, slot):
    if model in ("M3100A", "M3102A"):
        module = keysightSD1.SD_AIN()
    else:
        module = keysightSD1.SD_AOU()

    try:
        print("Opening {} module in slot {} and chassis {} to check UUID from k7z file".format(model, slot, chassis))

        moduleID = module.openWithOptions(model, chassis, slot, options = "simulate=true") # module info isn't important in simulation mode
        if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

        uuid = module.FPGAGetKernelUUIDFromK7z(k7z_file)
        if isinstance(uuid, int) and uuid < 0: raise ValueError("FPGAGetKernelUUIDFromK7z error {}: {}".format(uuid, keysightSD1.SD_Error.getErrorMessage(uuid)))

        print("{} has the UUID {}".format(k7z_file, uuid))

    finally:
        module.close()
        print("{} module in slot {} and chassis {} closed after UUID is read from k7z file".format(model, slot, chassis))

    return uuid

def get_module_options(model, chassis, slot):
    if model in ("M3100A", "M3102A"):
        module = keysightSD1.SD_AIN()
    else:
        module = keysightSD1.SD_AOU()

    try:
        print("Opening {} module in slot {} and chassis {} to check module options.".format(model, slot, chassis))

        moduleID = module.openWithSlot(model, chassis, slot)
        if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

        options_dict = {}
        for option in ("model", "channels", "clock", "memory", "modulation", "dual_modulation", "up_modulation", "down_modulation", "onboard_dc", "streaming", "fpga", "fpga_programmable", "hvi"):
            # Add option to the dictionary
            options_dict[option] = module.getOptions(option)

            print("{}: {}".format(option, module.getOptions(option)))

    finally:
        module.close()
        print("{} module in slot {} and chassis {} closed after module info is obtained".format(model, slot, chassis))

    return options_dict

def get_module_temperature(model, chassis, slot):
    if model in ("M3100A", "M3102A"):
        module = keysightSD1.SD_AIN()
    else:
        module = keysightSD1.SD_AOU()

    try:
        print("Opening {} module in slot {} and chassis {} to check module temperature".format(model, slot, chassis))

        moduleID = module.openWithSlot(model, chassis, slot)
        if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

        temperature = module.getTemperature()
        if isinstance(temperature, int) and temperature < 0: raise ValueError("getTemperature error {}: {}".format(temperature, keysightSD1.SD_Error.getErrorMessage(moduleID)))
        print("Temperature: {}".format(temperature))

    finally:
        module.close()
        print("{} module in slot {} and chassis {} closed after module info is obtained".format(model, slot, chassis))

        return temperature

def print_chassis_config():
    module_count = keysightSD1.SD_AOU.moduleCount() # Returns the number of Keysight SD1 modules (M31xxA/M32xxA/M33xxA) installed in the system.
    slot_list = [] # (chassis, slot)
    for i in range(module_count):
        slot = keysightSD1.SD_AOU.getSlotByIndex(i)
        chassis = keysightSD1.SD_AOU.getChassisByIndex(i)
        slot_list.append((chassis, slot))

    # Sort list of tuple by first element then second
    slot_list = sorted(slot_list, key=lambda x: (x[0], x[1]))

    print("Chassis slot configuration")
    for chasis, slot in slot_list:
        name = keysightSD1.SD_AOU.getProductNameBySlot(chassis, slot)
        serial_number = keysightSD1.SD_AOU.getSerialNumberBySlot(chassis, slot)
        
        if slot < 10:
            print("Chassis {}, slot {},  model {}, S/N {}".format(chassis, slot, name, serial_number)) # add space to keep lines aligned
        else:
            print("Chassis {}, slot {}, model {}, S/N {}".format(chassis, slot, name, serial_number))

def run_self_test(model, chassis, slot):
    if model in ("M3100A", "M3102A"):
        module = keysightSD1.SD_AIN()
    else:
        module = keysightSD1.SD_AOU()

    try:
        print("Opening {} module in slot {} and chassis {} to run self-test.".format(model, slot, chassis))

        moduleID = module.openWithSlot(model, chassis, slot)
        if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

        error = module.runSelfTest()
        if isinstance(error, int) and error < 0: raise ValueError("runSelfTest error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))

    finally:
        module.close()
        print("{} module in slot {} and chassis {} closed after self-test.".format(model, slot, chassis))

def install_firmware(model, chassis, slot, firmware_path):
    if model in ("M3100A", "M3102A"):
        module = keysightSD1.SD_AIN()
    else:
        module = keysightSD1.SD_AOU()

    # Ask the user to confirm the installation
    user_input = input("Do you want to install the firmware in the {} module in slot {} and chassis {}? (y/n)".format(firmware_path, model, slot, chassis))
    
    if user_input.lower() == "y" or user_input.lower() == "yes":
        print("Opening {} module in slot {} and chassis {} to load firmware.".format(model, slot, chassis))

        try:
            moduleID = module.openWithSlot(model, chassis, slot)
            if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

            error = module.FPGAload(firmware_path)
            if isinstance(error, int) and error < 0: raise ValueError("FPGAload error {}: {}".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
    
        except:
            module.close()
            print("{} module in slot {} and chassis {} closed after loading firmware.".format(model, slot, chassis))

        # Get AWG's registers info
        try:
            nb_FPGA_registers = 0
            for i in range(1, 100):
                registers = module.FPGAgetSandBoxRegisters(i)
                if isinstance(registers, int) and registers < 0:
                    error = registers
                    raise ValueError("AWG FPGAgetSandBoxRegisters() error {}: {}\n Check the number of registers to read.\n This function won't work with the default firmware.".format(error, keysightSD1.SD_Error.getErrorMessage(error)))
                else:
                    nb_FPGA_registers += 1
        except ValueError:
            registers = module.FPGAgetSandBoxRegisters(nb_FPGA_registers) # need to use FPGAload or FPGAconfigureFromK7z before calling this function
            print("The firmware has {} registers.".format(nb_FPGA_registers))
            if nb_FPGA_registers > 0:
                print("Registers contained in the module:")
                for register in registers:
                    print("Register name: {}".format(register.Name.rstrip("\x00")))
                    print("\tRegister size [bytes]: {}".format(register.Length))
                    print("\tRegister address offset [bytes]: {}".format(register.Address))
                    print("\tRegister access: {}".format(register.AccessType))
        finally:
            module.close()
            print("{} module in slot {} and chassis {} closed after loading firmware.".format(model, slot, chassis))

    else:
        print("Firmware installation cancelled.")

def convert_voltage_to_int(model, chassis, slot, voltage):
    if model in ("M3201A", "M3202A"):
        module = keysightSD1.SD_AOU()
    else:
        raise ValueError("Model {} not supported. Supported models are M3201A and M3202A".format(model))

    try:
        print("Opening {} module in slot {} and chassis {} to convert voltage to int.".format(model, slot, chassis))

        moduleID = module.openWithSlot(model, chassis, slot)
        if moduleID < 0: raise ValueError("Module open error {}: {}".format(moduleID, keysightSD1.SD_Error.getErrorMessage(moduleID)))

        int_value = module.voltsToInt(voltage)
        print("Convert volt to int: {}".format(int_value))

    finally:
        module.close()
        print("{} module in slot {} and chassis {} closed after converting voltage to int.".format(model, slot, chassis))



if __name__ == "__main__":
    firmware_library = FirmwareVersionTracker()
    firmware_library.load_database(r"firmware_database.yaml")
    print(firmware_library)
    print("")
    firmware_library.save_database(r"firmware_database.yaml")

    firmware_library.search_uuid("f85d9238-84be-e288-b426-e1f82b4c4fad")

    firmware_path = r"Sweeper\PathWave FPGA firmwares\M3202A VG CC12 v3\SD1 030408\virtual_gates_M3202A_CC12_card1_v3.k7z"
    
    model, chassis, slot = "M3100A", 1, 9
    install_firmware(model, chassis, slot, firmware_path)
    firmware_library.check_module_firmware(model, chassis, slot)

    get_uuid_from_k7z(firmware_path,  model, chassis, slot)

    M3202A_voltage_registers_firmware = firmware_library.get_fw("Voltage_registers_firmware_SD1_HVI", "M3202A", "04.03.00")

    print_chassis_config()
    options = get_module_options("M3201A", 1, 7)
    print(options)
    get_module_temperature("M3202A", 1, 10)
    convert_voltage_to_int("M3202A", 1, 10, 1)
    run_self_test("M3202A", 1, 10) # -8032: SD1 error: Wrong hardware response.



 