# -*- coding: utf-8 -*-
"""
Created on Tue Feb  9 11:32:35 2021

@author: Larissa Njejimana, Marc-Antoine Roux

See 10.1103/RevModPhys.75.1
See http://savoirs.usherbrooke.ca/handle/11143/5054
"""

import numpy as np
import matplotlib.pyplot as plt


# plt.close("all")

# DC Sweep parameters : initial and final voltages + number of steps
Vi_1D = -1.5
Vf_1D = 1.5
Vi_2D = -1.5
Vf_2D = 1.5
nCycles_1D = 40
nCycles_2D = 40

x = np.linspace(Vi_1D, Vf_1D, nCycles_1D)
y = np.linspace(Vi_2D, Vf_2D, nCycles_2D)

# apply Keysight digitizer resolution (Q2.14 format, range -2V to +1.999V)
DIG_factor = 2 / (2**15-1)
x = np.round(x / DIG_factor)
y = np.round(y / DIG_factor)
x = x * DIG_factor
y = y * DIG_factor


# Quantum dot sumulator capacitance values set in the FPGA as constants
Cg1=1.4
Cg2=1.2
CL=0.4
CR=0.4
N_max=4
kBT=0.01
e=1.0

# # more transitions
# Cg1=3
# Cg2=3
# CL=0.4
# CR=0.4
# N_max=8
# kBT=0.01
# e=1.0

# initialize Cm and increment step
Cm_initial = 0.0
Cm_final = 10.0
Cm_step = 0.5

nb_VideoLoops = 1 #int((Cm_final - Cm_initial)/Cm_step) + 1
Cm = Cm_initial

firstPlot = 1
usePcolorMesh = 1

# start video mode. Cm increments with the loop.
for i in range(nb_VideoLoops):

    C1 = CL+Cg1+Cm
    C2 = CR+Cg2+Cm
    Ec1 = e**2*(C2/(C1*C2-Cm**2))
    Ec2 = e**2*(C1/(C1*C2-Cm**2))
    Ecm = e**2*(Cm/(C1*C2-Cm**2))

    Z = 0
    moy = 0

    occupation = []
    for Vg2 in y:
        occupation_row = []

        for Vg1 in x:
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
            if Z == 0: print("Z = 0, nb_electrons = ",nb_electrons)

            occupation_row.append(nb_electrons)
            nb_electrons = np.round(nb_electrons/ 2**-12)
            nb_electrons = nb_electrons * 2**-12
            Z = 0
            moy = 0

        occupation.append(occupation_row)

    # convert from list to array
    occupation = np.array(occupation)

    # apply Digitizer output resolution (Q4.12 format, range -8V to +7.999, resolution=2^-12)
    out_factor = 2**-12
    occupation = np.round(occupation/ out_factor)
    occupation = occupation * out_factor

    # Plot derivative of the stability diagram
    derivative = np.gradient(occupation, axis=0)

    # Axes
    xv, yv = np.meshgrid(x, y)

    if (firstPlot == 1):
        firstPlot = 0

        plt.ion()
        plt.show()

        # fig = plt.figure(figsize=(8, 16),facecolor='white')
        #fig = plt.figure(figsize=(10, 8),facecolor='white')
        fig = plt.figure()

        ax1 = plt.subplot(111)

        # ax1 = plt.subplot(211)
        # ax2 = plt.subplot(212)

        if usePcolorMesh == 1:
            # plot Stability diagram
            quad1 = ax1.pcolormesh(xv, yv, occupation, cmap="viridis", shading="gouraud")
            #quad1 = ax1.pcolormesh(xv, yv, occupation, cmap="viridis", vmin = 0.0, vmax=N_max, shading="gouraud")
            # quad1 = ax1.pcolormesh(xv, yv, occupation, cmap="viridis", vmin = 0.0, vmax=N_max, shading="auto")


            # # plot derivative of the stability diagram
            # quad2 = ax2.pcolormesh(xv, yv, derivative, cmap="viridis", vmin = np.amin(derivative), vmax=np.amax(derivative), shading="gouraud")
            # # quad2 = ax2.pcolormesh(xv, yv, derivative, cmap="viridis", vmin = np.amin(derivative), vmax=np.amax(derivative), shading="auto")

        else:
            # plot Stability diagram
            quad1 = ax1.imshow(occupation, cmap="viridis", vmin = 0.0, vmax=N_max,
                               extent =[x.min(), x.max(), y.min(), y.max()],
                               interpolation ='bilinear', origin ='lower')

            # # plot derivative of the stability diagram
            # quad2 = ax2.imshow(derivative, cmap="viridis", vmin = np.amin(derivative), vmax=np.amax(derivative),
            #                    extent =[x.min(), x.max(), y.min(), y.max()],
            #                    interpolation ='bilinear', origin ='lower')

        ax1.set_xlabel("Vg1 [V]")
        ax1.set_ylabel("Vg2 [V]")
        cbar1 = fig.colorbar(quad1, ax=ax1)
        cbar1.set_label("Nb of electrons", rotation=90)



        # ax2.set_xlabel("Vg1 [V]")
        # ax2.set_ylabel("Vg2 [V]")
        # cbar2 = fig.colorbar(quad2, ax=ax2)
        # cbar2.set_label("Conductance", rotation=90)


    else:

        if usePcolorMesh == 1:
            # update Stability diagram
            quad1.set_array(occupation.ravel()) # to use with pcolormesh shading="gouraud"
            # quad1.set_array(occupation[:-1,:-1].ravel()) # to use with pcolormesh shading="auto"

            # # update derivative of the stability diagram
            # quad2.set_array(derivative.ravel()) # to use with pcolormesh shading="gouraud"
            # # quad2.set_array(derivative[:-1,:-1].ravel()) # to use with pcolormesh shading="auto"

        else:
            # update Stability diagram
            quad1.set_array(occupation) # to use with imshow

            # # update derivative of the stability diagram
            # quad2.set_array(derivative) # to use with imshow


    ax1.set_title('Cm = %.2f' %Cm)
    fig.canvas.draw()
    fig.canvas.flush_events()
    # fig.canvas.manager.window.activateWindow()
    # fig.canvas.manager.window.raise_()

    # increment Cm
    Cm = Cm + Cm_step

plt.ioff()


print('End.')