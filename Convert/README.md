##  Convert all pic and vid in a folder and save them into sub folders with json to avoid re processing.

Defaults to a universal codec and jpg for social media.

Lowering the quality from 100 to 95 reduces file size significantly, the quality loss is unnoticable by the human eye.

--p For only pic.

--v For only vid.

--nine_sixteen Aspect ratio for YouTube.

--one_to_one Aspect ratio for YouTube.

--crop Crops the image instead of looking for a close resolution to match the aspect ratio.

--t 60 or trim to any duration

--debug shows extra debug messages.

python convert.py YanaSn0w1 ./downloads --output-dir ./downloads --debug --nine_sixteen
