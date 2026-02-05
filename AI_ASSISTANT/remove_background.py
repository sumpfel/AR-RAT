import cv2
import numpy as np
import os
import sys

def remove_green_background(image_path, output_path):
    print(f"Processing: {image_path}")
    
    # Read image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read {image_path}")
        return

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Define range of green color in HSV
    # Green is around 60 degrees. 
    # S and V should be high for "bright green"
    lower_green = np.array([35, 100, 100])
    upper_green = np.array([85, 255, 255])

    # Threshold the HSV image to get only green colors
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # Invert mask to get the foreground (mouth)
    mask_inv = cv2.bitwise_not(mask)
    
    # Optional: Morphological operations to clean up noise
    kernel = np.ones((3,3), np.uint8)
    mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_OPEN, kernel, iterations=1)
    mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_DILATE, kernel, iterations=1)

    # Split channels
    b, g, r = cv2.split(img)

    # Create alpha channel from the mask
    rgba = [b, g, r, mask_inv]
    result = cv2.merge(rgba, 4)

    # Save
    cv2.imwrite(output_path, result)
    print(f"Saved: {output_path}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "assets", "raw_mouths")
    out_dir = os.path.join(base_dir, "assets", "mouths")
    
    # Copy generated images from artifacts dir to raw_dir specifically for processing 
    # (assuming they might be there or user moves them, but for this task I will reference 
    # the artifacts I generated if I can find them, or just let the user run this on raw_dir)
    
    # AUTO-DETECT: Check for the generated artifacts in the known artifact path
    # NOTE: The agent generated them in /home/christof/.gemini/antigravity/brain/...
    # I should attempt to copy them if they exist there.
    artifact_dir = "/home/christof/.gemini/antigravity/brain/9701612e-d5e1-4471-b544-7fbced12b2bb"
    
    if not os.path.exists(raw_dir):
        os.makedirs(raw_dir)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Move artifacts to raw_dir
    if os.path.exists(artifact_dir):
        for f in os.listdir(artifact_dir):
            if f.startswith("mouth_") and f.endswith(".png") and "green" in f:
                src = os.path.join(artifact_dir, f)
                dst = os.path.join(raw_dir, f)
                # Just copy/overwrite
                img = cv2.imread(src)
                cv2.imwrite(dst, img)
                print(f"Imported artifact: {f}")

    # Process all images in raw_dir
    files = os.listdir(raw_dir)
    for f in files:
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            in_path = os.path.join(raw_dir, f)
            
            # Map filename to simple name (e.g. mouth_a_green_....png -> a.png)
            name_part = f.split('_')[1] # a, e, i, o, u, closed
            if name_part not in ['a', 'e', 'i', 'o', 'u', 'closed']:
                continue
                
            out_name = f"{name_part}.png"
            out_path = os.path.join(out_dir, out_name)
            
            remove_green_background(in_path, out_path)

if __name__ == "__main__":
    main()
