onbreak {quit -f}
onerror {quit -f}

vsim -t 1ps -lib xil_defaultlib quantum_dot_simulator_0_opt

do {wave.do}

view wave
view structure
view signals

do {quantum_dot_simulator_0.udo}

run -all

quit -force
