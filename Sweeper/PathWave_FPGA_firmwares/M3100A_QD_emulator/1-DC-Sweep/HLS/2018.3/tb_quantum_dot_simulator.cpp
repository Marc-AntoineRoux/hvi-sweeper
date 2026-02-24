#include "quantum_dot_simulator.h"


const int nbPts = 50;

const float golden_occupation[nbPts][nbPts]= {
	#include "golden_occupation.dat"
};

const float tolerance = 1e-03;

void array_linspace(float xi, float xf, int n, float *x);

int main()
{
	int i,j;
	int retval = 0;
	FILE *fp;
	FILE *fd;

	float occupation[nbPts][nbPts];

	float Vg1[nbPts];
	float Vg2[nbPts];

	// définir les plages de sweep de tension sur les grilles 1 et 2
	array_linspace(0, 1.5, nbPts, Vg1);
	array_linspace(0, 1.5, nbPts, Vg2);

	short V1;
	short V2;

	float Cm = 0.2;		// Capacitance between the two dots.

	//int Cm_int = (int) hls::round(Cm / Cm_factor);
	//short Cm_int = (short) hls::round(Cm / Cm_factor);
	//short Cm_int = (short) hls::round(Cm / Cm_factor.to_float());

	int differences = 0;
	float delta;

	// calculer l'occupation électronique en faisant un sweep 2D
	for(i = 0; i < nbPts; i++)
	{
		for(j = 0; j < nbPts; j++)
		{
			V1 = (short) hls::round(Vg1[i] / DIG_factor);
			V2 = (short) hls::round(Vg2[j] / DIG_factor);

			//occupation[j][i] = 1.0 * quantum_dot_simulator(V1, V2) / OUT_factor;
			//occupation[j][i] = 1.0 * quantum_dot_simulator(V1, V2, Cm_int) / OUT_factor;
			occupation[j][i] = 1.0 * quantum_dot_simulator(V1, V2, Cm) / OUT_factor;

		}
	}

	//write results in external file out.dat
	fp = fopen("out.dat","w");
	for(i = 0; i < nbPts; i++)
	{
		for(j = 0; j < nbPts; j++)
		{
			//fprintf(fp, "%lf\t", occupation[i][j]);
			fprintf(fp, "%g\t", occupation[i][j]);
		}
		fprintf(fp, "\n");
	}
	fclose(fp);

	// Compare the results file with the golden results
	fp = fopen("delta.dat","w"); //write differences in external file out.dat
	fd = fopen("diff.dat","w"); //write differences in external file out.dat
	for(i = 0; i < nbPts; i++)
	{
		for(j = 0; j < nbPts; j++)
		{
			delta = hls::abs(golden_occupation[i][j]-occupation[i][j]);
			//delta = fabsf(golden_occupation[i][j]-occupation[i][j]);
			fprintf(fp, "%g\t", delta );

			if (delta > tolerance)
			{
				differences ++;
				fprintf(fd, "%d\t", 1);
			}
			else
				fprintf(fd, "%d\t", 0);
		}
		fprintf(fp, "\n");
		fprintf(fd, "\n");
	}
	fclose(fp);
	fclose(fd);


	if (differences != 0)
	{
		printf("***************\n");
		printf("*** FAILED! ***\n");
		printf("***************\n");
		printf("Number of differences = %d\n", differences);
		retval = 1;
	}
	else
	{
		printf("*****************\n");
		printf("*** PASSED!!! ***\n");
		printf("*****************\n");
		retval = 0;
	}


	return retval;
}


// x = linspace(xi,xf,n)
void array_linspace(float xi, float xf, int n, float *x)
{
	int i;
	float step = (xf-xi) / (n-1);

	x[0] = xi;

	Array_linspace_Loop: for (i = 1; i < n; i++)
	{
		x[i] = xi + i*step;
	}
}
