from pyTFM.TFM_functions import calculate_deformation, TFM_tractions, strain_energy_points, contractillity
from pyTFM.plotting import show_quiver, plot_continuous_boundary_stresses
from pyTFM.stress_functions import lineTension
from pyTFM.grid_setup_solids_py import interpolation, prepare_forces, grid_setup, FEM_simulation, find_borders
from pyTFM.utilities_TFM import round_flexible
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage.morphology import binary_fill_holes
import os

## calculating a deformation field

# path to the images of beads after and before cell removal
# you can also provide arrays with dtype=int32.
folder = os.getcwd()
im_path1 = os.path.join(folder, "04after.tif")
im_path2 = os.path.join(folder, "04before.tif")

u, v, mask_val, mask_std = calculate_deformation(im_path1, im_path2, window_size = 100, overlap = 60)
# The unit of window size and overlap is pixels, so you need to adapt them according
# to your pixel size

# plotting the deformation field
fig1, ax = show_quiver(u, v, cbar_str="deformations\n[pixels]")# plotting


## calculating a traction forces

# important parameters:
ps1 = 0.201 # pixel size of the image of the beads
im1_shape = (1991, 2033) # dimensions of the image of the beads
ps2 = ps1*np.mean(np.array(im1_shape) / np.array(u.shape)) # pixel size of of the deformation field
young = 49000 # Young's modulus of the substrate
sigma = 0.49 # Poisson's ratio of the substrate
h = 300 # height of the substrate in µm, "infinite" is also accepted

tx, ty = TFM_tractions(u, v, pixelsize1=ps1, pixelsize2=ps2, h=h, young=young, sigma=sigma)
# This function assumes a finite substrate height unless you set h="infinite".

# plotting the traction field
fig2, ax = show_quiver(tx, ty, cbar_str="tractions\n[Pa]")

## measuring force generation


mask = plt.imread(os.path.join(folder, "force_measurement.png")).astype(bool)
mask = binary_fill_holes(mask) # the mask should be a single patch without holes
# changing the masks dimensions to fit to the deformation and traction field:
mask = interpolation(mask, dims=u.shape)

# Strain energy:
# Calculating a map of strain energy
energy_points = strain_energy_points(u, v, tx, ty, ps1, ps2) # J/pixel
# Calculating the total strain energy in the area of the cells
strain_energy = np.sum(energy_points[mask]) # 1.92*10**-13 J

# Contractillity
contractile_force, proj_x, proj_y, center = contractillity(tx, ty, ps2, mask) # 2.01*10**-6 N

## measuring stresses

# first mask: The area used for Finite Elements Methods.
# should encircle all forces generated by the cell colony
mask_FEM = plt.imread(os.path.join(folder, "FEM_area.png")).astype(bool)
mask_FEM = binary_fill_holes(mask_FEM) # the mask should be a single patch without holes
# changing the masks dimensions to fit to the deformation and traction field:
mask_FEM = interpolation(mask_FEM, dims=tx.shape)

# second mask: The area of the cells. Average stresses and other values are calculated only
# on the actual area of the cell, represented by this mask.
mask_cells = plt.imread(os.path.join(folder, "cell_borders.png")).astype(bool)
mask_cells = binary_fill_holes(mask_cells)
mask_cells = interpolation(mask_cells, dims=tx.shape)


# converting tractions (forces per surface area) to forces
# and correcting imbalanced forces and torques
fx, fy = prepare_forces(tx, ty, ps2, mask_FEM)
# construct FEM grid
nodes, elements, loads, mats = grid_setup(mask_FEM, -fx, -fy, sigma=0.5)
# performing FEM analysis
UG_sol, stress_tensor = FEM_simulation(nodes, elements, loads, mats, mask_FEM, verbose=True)

# mean normal stress
ms_map = ((stress_tensor[:, :, 0, 0] + stress_tensor[:, :, 1, 1]) / 2) / (ps2 * 10**-6)
ms = np.mean(ms_map[mask_cells]) # 0.0046 N/m

# coefficient of variation
cv = np.nanstd(ms_map[mask_cells]) / np.abs(np.nanmean(ms_map[mask_cells])) # 0.37 no unit

## measuring the line tension

# loading a mask of the cell borders
mask_borders = plt.imread(os.path.join(folder, "cell_borders.png")).astype(bool)

# identifying borders, counting cells, performing spline interpolation to smooth the borders
borders = find_borders(mask_borders, tx.shape)
# The borders object describes which points belong to a cell border, which borders belong to a cell
# and performs spline interpolation on the cell borders.
n_cells = borders.n_cells # For example you can get the number of cells here

# calculating the line tension along the cell borders. This includes an interpolation of the stress tensor.
lt, min_v, max_v = lineTension(borders.lines_splines, borders.line_lengths, stress_tensor, pixel_length=ps2)
# lt is a nested dictionary. The first key is the id of a cell border. For each cell border
# the line tension vectors ("t_vecs"), the normal and shear component of the line tension ("t_shear") and
# the normal vectors of the cell border ("n_vecs") is calculated at a large number of points.

# average norm of the line tension
# only borders not at colony edge are used.
lt_vecs = np.concatenate([lt[l_id]["t_vecs"] for l_id in lt.keys() if l_id not in borders.edge_lines])
avg_line_tension = np.mean(np.linalg.norm(lt_vecs, axis=1)) # 0.00595 N/m

# average normal component of the line tension
lt_normal = np.concatenate([lt[l_id]["t_normal"] for l_id in lt.keys() if l_id not in borders.edge_lines])
avg_normal_line_tension = np.mean(np.abs(lt_normal)) # 0.00592 N/m,
# here you can see that almost all line tension acts perpendicular to the cell borders.

# plotting the line tension
fig3, ax = plot_continuous_boundary_stresses([borders.inter_shape, borders.edge_lines, lt, min_v, max_v], cbar_style="outside")

# saving plots
fig1.savefig(os.path.join(folder, "deformation_field.png"))
fig2.savefig(os.path.join(folder, "traction_field.png"))
fig3.savefig(os.path.join(folder, "line_tension.png"))

# printing results
print("strain energy = ", str(round_flexible(strain_energy)))
print("contractillity = ", str(round_flexible(contractile_force)))
print("avg. mean normal stress = ", str(round_flexible(ms)))
print("coefficient of variation of mean normal stress = ", str(round_flexible(cv)))
print("avg. line tension = ", str(round_flexible(avg_line_tension)))
print("avg. normal line tension = ", str(round_flexible(avg_normal_line_tension)))

