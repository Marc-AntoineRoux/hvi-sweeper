# hvi-sweeper
HVI functions to quickly measure stability diagrams using M3xxxA AWG and digitizer modules from Keysight.

# Requirements
PathWave Test Sync Executive 2021

PathWave FPGA 2022 Update 1.0 (more recent versions might work but have not been fully tested)

M3201A AWG modules, M3202A AWG modules or M3100A digitizer modules (other M3xxxA modules might work with some modifications in the code)

# Usage
To test the code, run the "Sweeper2D_KS2201A.py" file with the current working directory set to the "hvi-sweeper" folder. It uses the parameters from the "experiment_config_Sweeper2D.yaml" config file. The custom firmware might need to be recompiled with PathWave FPGA if the firmware of your system's modules doesn't match with the firmware already compiled in the project. For this task, you can use the script in "pathwave_fpga_compilation.py". Here is a small diagram that shows the core functions of the code.

<img width="4126" height="2026" alt="functional diagram" src="https://github.com/user-attachments/assets/0b73daab-644d-46a3-b766-739bdbfc2115" />

Feel free to email me if you have any questions!

