import sys, os
from layerscan.core.pipeline import ProcessingPipeline
from layerscan.utils.config import Config, ProjectConfig

app_config = Config()
p_config = ProjectConfig(os.path.expanduser("~/.layerscan3d/projects/default"))
p_config.data["images_dir"] = "/Users/jose/Documents/Universidad/Biomateriales/Proyecto/CE3PRO_Gyroid_60%/"
p_config.data["stl_file"] = "/Users/jose/Documents/Universidad/Biomateriales/Proyecto/CE3PRO_Gyroid 60%.stl"
p_config.data["gcode_file"] = "/Users/jose/Documents/Universidad/Biomateriales/Proyecto/gcode_Gyroid 60%.gcode"
p_config.data["scale_mm_per_px"] = 0.05  # Assume something reasonable for 1920px = ~96mm

pipeline = ProcessingPipeline(p_config, app_config)

def dummy_progress(p, msg):
    print(f"[{p}%] {msg}")
pipeline.set_progress_callback(dummy_progress)

result = pipeline.run()

if result.reconstructed_mesh:
    mesh = result.reconstructed_mesh
    print("----- RECONSTRUCTION SUCCESS -----")
    print(f"Vertices: {len(mesh.vertices)}")
    print(f"Faces: {len(mesh.faces)}")
    print(f"Bounds: {mesh.bounds}")
    print(f"Extents: {mesh.extents}")
else:
    print("FAILED:", result.error)
