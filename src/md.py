#!/usr/bin/env python
# -*- coding: utf-8 -*-
# file: md.py

import ctypes as C
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D

CLIB = C.CDLL('../bin/libmd.so')

# Abreviaturas
flp = C.POINTER(C.c_float)

# Funciones de C
CLIB.primer_paso.argtypes = [flp, flp, flp, C.c_int, C.c_float]
CLIB.nueva_fza.argtypes = [flp, flp, C.c_int, C.c_float, C.c_float,
                           flp, C.c_int]
CLIB.nueva_fza_exacto.argtypes = [flp, flp, C.c_int, C.c_float, C.c_float]
CLIB.ultimo_paso.argtypes = [flp, flp, C.c_int, C.c_float]
CLIB.c_cont.argtypes = [flp, C.c_int, C.c_float]
CLIB.lennardjones_lut.argtypes = [flp, C.c_int, C.c_float]
CLIB.fuerza_lut.argtypes = [flp, flp, C.c_int, C.c_float]

CLIB.cinetica.argtypes = [flp, C.c_int]
CLIB.potencial.argtypes = [flp, C.c_int, C.c_float, flp, C.c_int, C.c_float]
CLIB.potencial_exacto.argtypes = [flp, C.c_int, C.c_float, C.c_float]

# Return types
CLIB.cinetica.restype = C.c_float
CLIB.potencial.restype = C.c_float
CLIB.potencial_exacto.restype = C.c_float

##############################
# Paso completo de MD
##############################


def paso(pos, vel, fza, N, L, h, rc, FZA_LUT, g):
    """ Da un paso en la simulacion usando las LUT. """
    p_pos = pos.ctypes.data_as(flp)
    p_vel = vel.ctypes.data_as(flp)
    p_fza = fza.ctypes.data_as(flp)
    p_FZA_LUT = FZA_LUT.ctypes.data_as(flp)

    CLIB.primer_paso(p_pos, p_vel, p_fza, N, h)
    CLIB.nueva_fza(p_pos, p_fza, N, L, rc, p_FZA_LUT, g)
    CLIB.ultimo_paso(p_vel, p_fza, N, h)
    CLIB.c_cont(p_pos, N, L)


def paso_exacto(pos, vel, fza, N, L, h, rc):
    """ Da un paso en la simulacion de forma exacta. """
    p_pos = pos.ctypes.data_as(flp)
    p_vel = vel.ctypes.data_as(flp)
    p_fza = fza.ctypes.data_as(flp)

    CLIB.primer_paso(p_pos, p_vel, p_fza, N, h)
    CLIB.nueva_fza_exacto(p_pos, p_fza, N, L, rc)
    CLIB.ultimo_paso(p_vel, p_fza, N, h)
    CLIB.c_cont(p_pos, N, L)

##############################
# Funciones auxiliares
##############################

def transforma_1D(x, y, z):
    ''' Recibe las coordenadas X, Y, Z y las convierte al 3N de C. '''
    assert x.size == y.size == z.size
    return np.array([x, y, z]).T.reshape(x.size * 3)


def transforma_xyz(vector):
    ''' Recibe el vector 3N mezclado y lo convierte en X, Y, Z. '''
    assert vector.ndim == 1
    N = vector.size
    assert N % 3 == 0
    aux = np.reshape(vector, (N // 3, 3)).T
    return aux[0], aux[1], aux[2]


def llenar_pos(N, L):
    ''' Setup para las posiciones y velocidades iniciales. '''

    # Toma la parte entera de la raiz cubica de N
    lado = int(N**(1.0 / 3.0))
    # Calcula el numero de lugares generados
    particulas = lado ** 3
    # Si las particulas no entran en la caja de lado M aumenta su tamano
    if particulas < N:
        lado += 1

    # Calcula la mitad de la separacion entre particulas
    s = L / lado / 2

    # Genera un vector
    aux = np.linspace(s, L - s, lado, dtype=float)
    x, y, z = np.meshgrid(aux, aux, aux, indexing='ij')
    pos = transforma_1D(x, y, z)

    return pos[0:3 * N].astype(C.c_float)


def llenar_vel(N, T):
    ''' Setup para las velocidades '''
    vel = np.random.normal(loc=0, scale=T**0.5, size=3 * N)
    vel -= np.mean(vel)

    return vel.astype(C.c_float)


def ver_pos(pos, vel=None, L=None, ax=None):
    if ax is None:
        plt.ion()
        fig, ax = plt.subplots(subplot_kw=dict(projection='3d'))

    if L is not None:
        ax.set_xlim([0, L])
        ax.set_ylim([0, L])
        ax.set_zlim([0, L])

    x, y, z = transforma_xyz(pos)
    scatter = ax.scatter(x, y, z)

    if vel is not None:
        vx, vy, vz = transforma_xyz(vel)
        quiver = ax.quiver(x, y, z, vx, vy, vz)
    else:
        quiver = None

    return fig, ax, scatter, quiver


##############################
# Configuracion
##############################

# Parametros externos
N = 512 # Nr de partiulas
rho = 0.8442 # Densidad
h = 0.001 # Paso temporal
T = 0.728 # Temperatura
g = 10000 # Precision de las Lookup-tables
niter = 1000 # Nr de iteraciones que se van a realizar

tiempo = np.arange(niter)

# Parametros internos
L = (N / rho)**(1.0 / 3.0) # Longitud de la caja
rc = 2.5 # Distancia de corte para el potencial y la fuerza
long_lut = int(g*rc) # Longitud de las Lookup-tables

# Configuracion inicial de posiciones y velocidades
pos = llenar_pos(N, L)
vel = llenar_vel(N, T)

# Memoria para las fuerzas
fza = np.zeros(3 * N, dtype=C.c_float)

# Memoria para las LUT
LJ_LUT = np.zeros(int(g * rc), dtype=C.c_float)
FZA_LUT = np.zeros(int(g * rc), dtype=C.c_float)

# Memoria para la energia
energia = np.zeros(niter, dtype=float)
cinetica = np.zeros(niter, dtype=float)
potencial = np.zeros(niter, dtype=float)

# Llenar las LUT
p_lj_lut = LJ_LUT.ctypes.data_as(flp)
p_fza_lut = FZA_LUT.ctypes.data_as(flp)
CLIB.lennardjones_lut(p_lj_lut, long_lut, rc)
CLIB.fuerza_lut(p_fza_lut, p_lj_lut, long_lut, rc)

# Punteros de las posiciones y velocidades
p_pos = pos.ctypes.data_as(flp)
p_vel = vel.ctypes.data_as(flp)


##############################
# Animacion provisoria
##############################


# plt.ion()
# fig, ax = plt.subplots(subplot_kw=dict(projection='3d'))
#
# ax.set_xlim([0, L])
# ax.set_ylim([0, L])
# ax.set_zlim([0, L])
#
# x, y, z = transforma_xyz(pos)
# scatter = ax.scatter(x, y, z)
# vx, vy, vz = transforma_xyz(vel)
# quiver = ax.quiver(x, y, z, vx, vy, vz)

# Variable auxiliar para elegir si resolver de forma exacta o no.
# 1: Calcula potencial y fuerza de forma exacta
# 0: Calcula potencial y fuerza mediante Lookup-tables
exacto = 0

for i in range(niter):
    if exacto:
        # Exacto
        paso_exacto(pos, vel, fza, N, L, h, rc)
        potencial[i] = CLIB.potencial_exacto(p_pos, N, L, rc)
    else:
        # Con Lookup-table
        paso(pos, vel, fza, N, L, h, rc, FZA_LUT, g)
        potencial[i] = CLIB.potencial(p_pos, N, L, p_lj_lut, g, rc)


    cinetica[i] = CLIB.cinetica(p_vel, N)
    energia[i] = cinetica[i] + potencial[i]

    # ax.cla()
    # x, y, z = transforma_xyz(pos)
    # scatter = ax.scatter(x, y, z)
    # vx, vy, vz = transforma_xyz(vel)
    # # quiver = ax.quiver(x, y, z, vx, vy, vz)
    # ax.set_xlim([0, L])
    # ax.set_ylim([0, L])
    # ax.set_zlim([0, L])
    # plt.draw()
    # plt.pause(0.0001)

path = '../datos/'
name = 'ej1a'

# Desviaciones de cada energia (Medido despues de termalizar)
sigma_cinetica = np.std(cinetica[400:])
sigma_potencial = np.std(potencial[400:])
sigma_energia = np.std(energia[400:])

# Valores medios (Medido despues de termalizar)
avg_cinetica = np.mean(cinetica[400:])
avg_potencial = np.mean(potencial[400:])
avg_energia = np.mean(energia[400:])

np.save(path + name + '_avg_energia', energia)
np.save(path + name + '_avg_cinetica', cinetica)
np.save(path + name + '_avg_potencial', potencial)
np.save(path + name + '_tiempo', tiempo)

print("Energia potencial = " + str(avg_potencial) + " +- " + str(sigma_potencial))
print("Energia cinetica = " + str(avg_cinetica) + " +- " + str(sigma_cinetica))
print("Energia total = " + str(avg_energia) + " +- " + str(sigma_energia))

# Grafica las tres energias en el mismo grafico
# plt.ion()
# fig2, ax2 = plt.subplots(1)
# ax2.plot(tiempo, energia, 'k.')
# ax2.plot(tiempo, cinetica, 'r.')
# ax2.plot(tiempo, potencial, 'b.')
# plt.xlabel(r'Tiempo')
# plt.ylabel('Energia')
# plt.show()
#
# # Grafica la cinetica y la potencial en un corto rango
# # Para mostrar que se complementan
# plt.ion()
# fig3, ax3 = plt.subplots(2, sharex=True)
# ax3[0].plot(tiempo[400:900], cinetica[400:900], 'r.', label='Energia cinetica')
# ax3[1].plot(tiempo[400:900], potencial[400:900], 'b.', label='Energia potencial')
# plt.xlabel(r'Tiempo')
# ax3[0].set_ylabel(r'Energia cinetica')
# ax3[1].set_ylabel(r'Energia potencial')
# ax3[0].set_title('Energia cinetica')
# ax3[1].set_title('Energia potencial')
# plt.show()
