# -*- coding: utf-8 -*-
"""
Created on Tue Oct  20 21:59:45 2020

@author: Larissa Njejimana, Marc-Antoine Roux

See 10.1103/RevModPhys.75.1
See http://savoirs.usherbrooke.ca/handle/11143/5054
"""

import numpy as np
import matplotlib.pyplot as plt
import csv


#plt.close("all")


nx, ny = (50,50)
x = np.linspace(0, 1.5, nx)
y = np.linspace(0, 1.5, ny)

# apply digitizer resolution (Q2.14 format, range -2V to +1.999V)
DIG_factor = 2 / (2**15-1)
x = np.round(x / DIG_factor)
y = np.round(y / DIG_factor)
x = x * DIG_factor
y = y * DIG_factor
#x = x.astype('float32')
#y = y.astype('float32')

Cg1=1.4
Cg2=1.2
Cm=0.2
CL=0.4
CR=0.4
N_max=4
kBT=0.01
e=1.0
C1 = CL+Cg1+Cm
C2 = CR+Cg2+Cm
Ec1 = e**2*(C2/(C1*C2-Cm**2))
Ec2 = e**2*(C1/(C1*C2-Cm**2))
Ecm = e**2*(Cm/(C1*C2-Cm**2))

Z = 0
moy = 0

occupation = []
for Vg1 in x:
    occupation_row = []

    for Vg2 in y:
        for N2 in range(N_max+1): # loop from [0, N_max]
            for N1 in range(N_max+1):

                param1 = 0.5*N1**2*Ec1+0.5*N2**2*Ec2+N1*N2*Ecm

                param2 = -1/e*(Cg1*Vg1*(N1*Ec1+N2*Ecm)+Cg2*Vg2*(N1*Ecm+N2*Ec2))

                param3 = 1/e**2*(0.5*Cg1**2*Vg1**2*Ec1+0.5*Cg2**2*Vg2**2*Ec2+Cg1*Vg1*Cg2*Vg2*Ecm)

                E = param1 + param2

                E = E + param3

                Z = Z + np.exp(-E/kBT)

                moy = moy + (N1+N2)*np.exp(-E/kBT)

                param1 = 0


        nb_electrons = moy/Z

        occupation_row.append(nb_electrons)
        nb_electrons = np.round(nb_electrons/ 2**-12)
        nb_electrons = nb_electrons * 2**-12
        Z = 0
        moy = 0

    occupation.append(occupation_row)

occupation = np.array(occupation)
occupation = np.transpose(occupation)


# apply output resolution (Q4.12 format, range -8V to +7.999, resolution=2^-12)
out_factor = 2**-12
occupation = np.round(occupation/ out_factor)
occupation = occupation * out_factor

# write occupation in a csv file
#with open(r"C:\Larissa\0-Quantum-Dot-Simulator\1-DC-Sweep\HLS\2017.3\golden_occupation.dat", 'w', newline='') as file:
with open(r"C:\Larissa\0-Quantum-Dot-Simulator\2-ParknFly\Cm-variable\HLS\golden_occupation.dat", 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerows(occupation)


# plot Stability diagram
xv, yv = np.meshgrid(x, y)
plt.figure()
plt.pcolormesh(xv,yv,occupation,cmap="viridis",shading="auto")
plt.xlabel("Vg1 [V]")
plt.ylabel("Vg2 [V]")
plt.title('Cm = %.2f' %Cm)
cbar = plt.colorbar()
cbar.set_label("Nb of electrons", rotation=90)

# Derivative of the stability diagram
derivative = np.gradient(occupation, axis=0)
plt.figure()
plt.pcolormesh(xv,yv,derivative,cmap="viridis",shading="auto")
plt.xlabel("Vg1 [V]")
plt.ylabel("Vg2 [V]")
plt.title('Cm = %.2f' %Cm)
cbar = plt.colorbar()
cbar.set_label("Conductance", rotation=90)

plt.show()