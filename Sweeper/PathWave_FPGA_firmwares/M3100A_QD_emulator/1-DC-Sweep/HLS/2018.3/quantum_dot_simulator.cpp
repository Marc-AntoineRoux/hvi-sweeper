#include "quantum_dot_simulator.h"


/**
 * Calculate electronic occupation
 *
 * @param 		Vg1 Voltage on gate 1.
 * @param 		Vg2 Voltage on gate 2.
 * @return 		Average number of electrons in the double dot.
 */
short quantum_dot_simulator(short V1, short V2, const float HVI_Cm)
{
#pragma HLS PIPELINE II=5
#pragma HLS ALLOCATION instances=fmul operation

	const float Cm = HVI_Cm;		// Capacitance between the two dots.

	const float C1 = CL + Cg1 + Cm;
	const float C2 = CR + Cg2 + Cm;
	const float Cm_carre = Cm * -Cm; //avoid using fsub later
	float C_arg = C1 * C2;
	C_arg += Cm_carre;

	float C_e_arg = e_carre/C_arg;
	C_e_arg *= inv_kBT;

	const float E_C1 = C2;
	const float E_C2 = C1;
	const float E_Cm = Cm;

	const float Vg1 = V1 * DIG_factor;
	const float Vg2 = V2 * DIG_factor;
	const float Cg1_Vg1 = Cg1 * Vg1;
	const float Cg2_Vg2 = Cg2 * Vg2;
	const float Vg1_carre = Vg1 * Vg1;
	const float Vg2_carre = Vg2 * Vg2;

	char N1, N2;
	float N1_carre;
	float N2_carre;
	float tmp1;
	float tmp2;
	float tmp3;
	float tmp4;

	float param1;
	float param2;
	float E = 0;

	float ttmp1;
	float ttmp2;
	float ttmp3;
	float ttmp4;
	float ttmp5;
	float ttmp6;
	float ttmp7;


	float arg = 0;
	float exp_arg = 0;
	float sum_Z[N_max+1] = {};
	float sum_moy[N_max+1] = {};
	float sumsum_moy = 0;
	float sumsum_Z = 0;
	float tmp_Z = 0;
	float tmp_moy = 0;
	float nb_electrons = 0;
	short t_nb_electrons;

	// calcul param3 = 1/e**2*(0.5*Cg1**2*Vg1**2*Ec1+0.5*Cg2**2*Vg2**2*Ec2+Cg1*Vg1*Cg2*Vg2*Ecm)
	ttmp4 = Cg1_carre*Vg1_carre ;
	ttmp4 *= E_C1 ;

	ttmp5 = Cg2_carre*Vg2_carre;
	ttmp5 *= E_C2;

	ttmp6 = ttmp4 + ttmp5;
	ttmp6 *= 0.5;

	ttmp7 = Cg1_Cg2*Vg1;
	ttmp7 *= Vg2;
	ttmp7 *= E_Cm;

	ttmp7 += ttmp6;
	const float param3 = ttmp7 * e_carre_inv;

	Outer_Loop: for(N2 = 0; N2 <= N_max; N2++)
	{
		Inner_Loop:for(N1 = 0; N1 <= N_max; N1++)
		{
			//E = param1 + param2 + param3;

			// Calcul param1 = 0.5*N1**2*Ec1+0.5*N2**2*Ec2+N1*N2*Ecm
			N1_carre = N1 * N1;
			N2_carre = N2 * N2;

			tmp1 = N1_carre*E_C1;
			tmp2 = N2_carre*E_C2;
			tmp3 = tmp1 + tmp2;
			tmp3 *= 0.5;

			tmp4 = N1 * N2 ;
			tmp4 *= E_Cm ;

			param1 = tmp3 + tmp4;

			// Calcul param2 = -1/e*(Cg1*Vg1*(N1*Ec1+N2*Ecm)+Cg2*Vg2*(N1*Ecm+N2*Ec2))
			ttmp1 = N1*E_C1;
			ttmp1 += N2*E_Cm;
			ttmp1 *=  Cg1_Vg1;

			ttmp2 = N1*E_Cm;
			ttmp2 += N2*E_C2;
			ttmp2 *=  Cg2_Vg2;

			ttmp3 = ttmp1 + ttmp2;
			param2 = ttmp3 * e_abs_inv;

			E = param1 + param2 + param3;

			arg = E * C_e_arg;

			exp_arg = hls::exp(arg);

			sum_Z[N2] += exp_arg;
			tmp_moy = N1+N2;
			tmp_moy *= exp_arg;
			sum_moy[N2] += tmp_moy;

		}

		sumsum_Z += sum_Z[N2];
		sumsum_moy += sum_moy[N2];

	}


	if (sumsum_Z == 0)
	{
		return 0;
	}
	else
	{
		nb_electrons = sumsum_moy/sumsum_Z;
		nb_electrons *= OUT_factor;

		t_nb_electrons = hls::round(nb_electrons);

		return t_nb_electrons;
	}


}
