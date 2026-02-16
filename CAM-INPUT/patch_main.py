
with open("main.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_translation_block = False

for i, line in enumerate(lines):
    # Detect the START of the problematic block (the one running every frame)
    # It starts around line 654 with "if translation_active:"
    # But wait, we have OTHER "if translation_active" blocks earlier.
    # The one we want to patch is near the END of the loop, followed by "global is_translating".
    
    if "if translation_active:" in line:
        # Look ahead to see if it contains "global is_translating"
        is_target_block = False
        for j in range(i+1, min(i+10, len(lines))):
            if "global is_translating" in lines[j]:
                is_target_block = True
                break
        
        if is_target_block:
            in_translation_block = True
    
    if in_translation_block:
        # If we hit "else:", we are in the else block of this specific if
        if "else:" in line and "if" not in line: # strictly else
             pass 
        
        # If we hit the next big block (e.g. UDP sending), stop
        if "Prepare Gesture UDP Packet" in line:
            in_translation_block = False
    
    # Apply commenting logic
    if in_translation_block:
        if "set_window_geometry" in line:
            if not line.strip().startswith("#"):
                new_lines.append("# " + line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("main.py", "w") as f:
    f.writelines(new_lines)
