vlib work
vlib riviera

vlib riviera/xbip_utils_v3_0_9
vlib riviera/axi_utils_v2_0_5
vlib riviera/xbip_pipe_v3_0_5
vlib riviera/xbip_dsp48_wrapper_v3_0_4
vlib riviera/xbip_dsp48_addsub_v3_0_5
vlib riviera/xbip_dsp48_multadd_v3_0_5
vlib riviera/xbip_bram18k_v3_0_5
vlib riviera/mult_gen_v12_0_14
vlib riviera/floating_point_v7_1_7
vlib riviera/xil_defaultlib

vmap xbip_utils_v3_0_9 riviera/xbip_utils_v3_0_9
vmap axi_utils_v2_0_5 riviera/axi_utils_v2_0_5
vmap xbip_pipe_v3_0_5 riviera/xbip_pipe_v3_0_5
vmap xbip_dsp48_wrapper_v3_0_4 riviera/xbip_dsp48_wrapper_v3_0_4
vmap xbip_dsp48_addsub_v3_0_5 riviera/xbip_dsp48_addsub_v3_0_5
vmap xbip_dsp48_multadd_v3_0_5 riviera/xbip_dsp48_multadd_v3_0_5
vmap xbip_bram18k_v3_0_5 riviera/xbip_bram18k_v3_0_5
vmap mult_gen_v12_0_14 riviera/mult_gen_v12_0_14
vmap floating_point_v7_1_7 riviera/floating_point_v7_1_7
vmap xil_defaultlib riviera/xil_defaultlib

vcom -work xbip_utils_v3_0_9 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_utils_v3_0_vh_rfs.vhd" \

vcom -work axi_utils_v2_0_5 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/axi_utils_v2_0_vh_rfs.vhd" \

vcom -work xbip_pipe_v3_0_5 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_pipe_v3_0_vh_rfs.vhd" \

vcom -work xbip_dsp48_wrapper_v3_0_4 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_dsp48_wrapper_v3_0_vh_rfs.vhd" \

vcom -work xbip_dsp48_addsub_v3_0_5 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_dsp48_addsub_v3_0_vh_rfs.vhd" \

vcom -work xbip_dsp48_multadd_v3_0_5 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_dsp48_multadd_v3_0_vh_rfs.vhd" \

vcom -work xbip_bram18k_v3_0_5 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/xbip_bram18k_v3_0_vh_rfs.vhd" \

vcom -work mult_gen_v12_0_14 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/mult_gen_v12_0_vh_rfs.vhd" \

vcom -work floating_point_v7_1_7 -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/floating_point_v7_1_vh_rfs.vhd" \

vcom -work xil_defaultlib -93 \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulbkb.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulcud.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simuldEe.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simuleOg.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulfYi.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulg8j.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulhbi.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulibs.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/vhdl/quantum_dot_simulator.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_fadd_2_full_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_fcmp_0_no_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_fdiv_6_no_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_fexp_3_full_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_fmul_0_max_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.ip_user_files/ipstatic/hdl/ip/quantum_dot_simulator_ap_sitofp_0_no_dsp_32.vhd" \
"../../../../../2018.3_variable/Quantum-dot-simulator.srcs/sources_1/ip/quantum_dot_simulator_0/sim/quantum_dot_simulator_0.vhd" \

