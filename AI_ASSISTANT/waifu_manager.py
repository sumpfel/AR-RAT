import os
import json
import shutil

class WaifuManager:
    def __init__(self, assets_dir):
        self.assets_dir = assets_dir
        self.waifu_dir = os.path.join(assets_dir, "waifus")
        self.config_path = os.path.join(self.waifu_dir, "waifu_config.json")
        self.config = {}
        
        self.load_config()
        self.scan_and_migrate()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"Error loading waifu config: {e}")
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving waifu config: {e}")

    def scan_and_migrate(self):
        """Scans for individual .json files and migrates them to the central config."""
        if not os.path.exists(self.waifu_dir):
            return

        migrated = False
        files = os.listdir(self.waifu_dir)
        
        for f in files:
            # Check for legacy JSON config files (e.g. "image.png.json")
            if f.endswith(".json") and f != "waifu_config.json":
                full_path = os.path.join(self.waifu_dir, f)
                
                # The image name is usually the filename minus ".json"
                # OR minus ".png.json" ? 
                # Based on previous code: json_path = path + ".json"
                # So if image is "waifu.png", json is "waifu.png.json"
                image_name = f[:-5] # Remove .json
                
                try:
                    with open(full_path, 'r') as json_file:
                        data = json.load(json_file)
                        if "mouth_rect" in data:
                            print(f"Migrating config for {image_name}...")
                            self.config[image_name] = {
                                "mouth_rect": data["mouth_rect"]
                            }
                            migrated = True
                    
                    # Delete old file
                    os.remove(full_path)
                except Exception as e:
                    print(f"Failed to migrate {f}: {e}")

        if migrated:
            self.save_config()

    def get_waifu_files(self):
        if not os.path.exists(self.waifu_dir):
            return []
        valid_exts = ('.png', '.jpg', '.jpeg', '.mp4', '.webm', '.gif')
        return [f for f in os.listdir(self.waifu_dir) if f.lower().endswith(valid_exts)]

    def get_mouth_rect(self, waifu_filename):
        if waifu_filename in self.config:
             return tuple(self.config[waifu_filename]["mouth_rect"])
        return None

    def set_mouth_rect(self, waifu_filename, rect):
        if waifu_filename not in self.config:
            self.config[waifu_filename] = {}
        
        self.config[waifu_filename]["mouth_rect"] = rect
        self.save_config()

    def import_waifu(self, source_path):
        import random
        if not os.path.exists(self.waifu_dir):
            os.makedirs(self.waifu_dir)
            
        filename = os.path.basename(source_path)
        dest_path = os.path.join(self.waifu_dir, filename)
        
        # Check if we are selecting a file that is ALREADY in the waifu dir
        abs_source = os.path.abspath(source_path)
        abs_dest = os.path.abspath(dest_path)
        
        if abs_source == abs_dest:
            return dest_path # Already there, do nothing
        
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(filename)
            dest_path = os.path.join(self.waifu_dir, f"{base}_{random.randint(1000,9999)}{ext}")
            
        shutil.copy2(source_path, dest_path)
        return dest_path
