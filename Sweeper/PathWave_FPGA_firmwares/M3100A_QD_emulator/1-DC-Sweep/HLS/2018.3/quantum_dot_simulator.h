
#ifndef __QUANTUM_DOT_SIMULATOR_H__
#define __QUANTUM_DOT_SIMULATOR_H__


#include "hls_math.h"

const char N_max = 4; 			// Maximum number of electrons in a dot.

const float Cg1 = 1.4;						// Capacitance of gate 1.
const float Cg2 = 1.2;						// Capacitance of gate 2.
/*
const float Cg1 = 3;						// Capacitance of gate 1.
const float Cg2 = 3;						// Capacitance of gate 2.
*/
const float CL = 0.4;						// Capacitance of the source.
const float CR = 0.4;						// Capacitance of the drain.
const float e = 1.0;						// Elementary charge. The default is 1.
const float kBT = 0.01;						// Thermal energy. The default is 0.01.

const float Cg1_carre = Cg1 * Cg1;
const float Cg2_carre = Cg2 * Cg2;
const float Cg1_Cg2 = Cg1 * Cg2;
const float inv_kBT = -1/kBT;

const float e_carre = e * e;
const float e_carre_inv = 1/e_carre;
const float e_abs = hls::abs(e);
const float e_abs_inv = -1/e_abs;


//**********************************//
//***** DIGITIZER parameters *******//
//**********************************//
const float fullscale = 2.0;
const float DIG_factor = fullscale / ((1 << 15) - 1); // Digitizer voltage to integer conversion factor (Q2.14 format)

const float OUT_factor = (1 << 12); // occupation value float to short conversion factor (Q4.12 format)


short quantum_dot_simulator(short V1, short V2, const float HVI_Cm);



#endif // __QUANTUM_DOT_SIMULATOR_H__
