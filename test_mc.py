import numpy as np
from skimage import measure

# Create a 3D sphere volume
Z, Y, X = np.ogrid[-20:20, -20:20, -20:20]
dist = np.sqrt(X**2 + Y**2 + Z**2)
volume = (dist < 15).astype(np.uint8) * 255

verts, faces, normals, _ = measure.marching_cubes(volume, level=127, step_size=4)
print(verts.min(axis=0), verts.max(axis=0))
