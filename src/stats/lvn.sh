#!/bin/bash

# Base directory containing the test directories
BASE_DIR="../../examples/test"

# Output file for all results in JSON format
OUTPUT_FILE="results_lvn.json"

# Clear or create the output file with an empty JSON array
echo "[]" > "$OUTPUT_FILE"

# Function to get current time in nanoseconds using python3
get_time_ns() {
    python3 -c 'import time; print(int(time.time() * 1e9))'
}

# Function to process a single .bril file and append results to a JSON array
process_file() {
    local file="$1"
    local dir_name="$2"
    local file_name=$(basename "$file" .bril)

    echo "Processing file: $file_name.bril in directory: $dir_name"

    # Initialize an empty array to store timing results
    timings=()

    # Loop to execute the processing 1000 times
    for i in {1..10}; do
        # Record the start time in nanoseconds
        start=$(get_time_ns)

        # Process the file and capture the output
        result=$(cat "$file" | bril2json | python3 ../local_value_numbering/local_value_numbering.py | bril2txt 2>&1)

        # Record the end time in nanoseconds
        end=$(get_time_ns)

        # Calculate the duration in nanoseconds
        duration=$((end - start))

        # Append the duration to the timings array
        timings+=("$duration")
    done

    # Convert the timings array to a JSON array
    timings_json=$(printf '%s\n' "${timings[@]}" | jq -R . | jq -s .)

    # Create a JSON entry for the file with timing data
    local json_entry=$(jq -n \
        --arg file "$file_name.bril" \
        --arg dir "$dir_name" \
        --arg result "$result" \
        --argjson timings "$timings_json" \
        '{file: $file, directory: $dir, result: $result, timings: $timings}')

    # Append the JSON entry to the output file
    jq --argjson new_entry "$json_entry" \
       '. += [$new_entry]' \
       "$OUTPUT_FILE" > temp.json && mv temp.json "$OUTPUT_FILE"
}

# Iterate over each directory within the base directory
for DIR in "$BASE_DIR"/*/; do
    # Get the directory name (e.g., 'lvn', 'df', etc.)
    DIR_NAME=$(basename "$DIR")

    # Skip non-directories or directories that are not in the list
    if [ ! -d "$DIR" ] || [[ ! "$DIR_NAME" =~ ^(df|dom|lvn|ssa|ssa_roundtrip|tdce|to_ssa)$ ]]; then
        continue
    fi

    echo "Processing directory: $DIR_NAME"

    # Iterate over each .bril file in the directory
    for FILE in "$DIR"*.bril; do
        # Skip if no .bril files are found
        if [ ! -f "$FILE" ]; then
            continue
        fi

        # Process the file
        process_file "$FILE" "$DIR_NAME"
    done
done

echo "Processing complete. Results saved to $OUTPUT_FILE."
