import subprocess

def compile_kfdk(project_name, cwd=r"C:\Program Files\Keysight\PathWave FPGA 2022 Update 1.0"):
    """
    Compile the kfdk project using PathWave FPGA. See the PathWave FPGA manual p.258 for the command line arguments.
    See https://stackoverflow.com/questions/4417546/constantly-print-subprocess-output-while-process-is-running

    Command Line Arguments for PathWave FPGA
    When PathWave FPGA is launched from a command line or script, there are a number of arguments
    to create or load projects, and control how the application operates.

    Usage: PathWave_FPGA (--project/-p/<no_switch> <ProjectFile (*.kfdk)>]
                         [--bsp/-b <BspName>] (--version/-v <BspVersion>] 
                         [--template/-t <TemplateName>] [-c <OptionName> <OptionValue>]
                         [--retarget/-r <ExistingProjectFile>] 
                         [--generate/-g <generationType>] [--synth_strat <strategy> 
                         -impl_strat <strategy>]
    
    Options:
    * <no_switch> or -p, [--project]:   Path to project file to open or create (*.kfdk)
    * -b, [--bsp]:                      Name of the BSP
    * -v, [--version]:                  Version of the BSP
    * -t, [--template]:                 Name of the BSP template to use
    * -r, [--retarget]:                 Path to existing project (*.kfdk) to retarget to different BSP configuration
    * -c:                               Name/Value configuration option pairs for the specified BSP, separated by space
    * -g, [--generate]:                 Type of generation: synthesis, implementation
    * --synth_strat:                    Synthesis strategy for generation
    * --impl_strat:                     Implementation strategy for generation
    * --directives:                     Step/Directive pairs for build steps that can have directives set, separated by space
    * -h, [--help]:                     Print usage message

    Parameters
    ----------
    project_name : str
        The name of the kfdk project to compile.
    cwd : str, optional
        The current working directory for the PathWave FPGA command, by default
        r"C:\Program Files\Keysight\PathWave FPGA 2022 Update 1.0"

    Raises
    ------
    subprocess.CalledProcessError
        If the compilation process fails.

    Returns
    -------
    None

    """
    cmd = 'PathWave_FPGA -p "{}" -g implementation'.format(project_name)
    popen = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True, cwd=cwd)
    for stdout_line in iter(popen.stdout.readline, ""):
        print(stdout_line, end='')
        if "Nothing left to do" in stdout_line:
            print("\n")
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

compile_kfdk(r"Sweeper\PathWave FPGA firmwares\M3202A VG CC12 v3\SD1 030408\virtual_gates_M3202A_CC12_card1_v3.kfdk")

