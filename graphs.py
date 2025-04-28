import os
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# Memory issue fix
pio.kaleido.scope.chromium_args = tuple([arg for arg in pio.kaleido.scope.chromium_args if arg != "--disable-dev-shm-usage"])

# Text size settings
TEXT_SIZE = 25
LEGEND_SIZE = TEXT_SIZE - 5

class DataError(Exception):
    """Custom exception for data-related errors"""
    pass

def get_selection(files):
    """Let user select files for combined plot"""
    print("\nFiles:", *[f"{i}. {f}" for i, f in enumerate(files, 1)], sep='\n')
    sel = input("\nEnter numbers or names separated by comma (,) for averaging or semicolon (;) for separate plots. Press enter to finish: ").strip()
    if not sel: return None
    if sel.lower() == 'all': return [files]  # Return as a single group
    
    # Split by semicolon first to get groups
    groups = [g.strip() for g in sel.split(';')]
    result = []
    
    for group in groups:
        if not group: continue
        
        # Handle each group (comma-separated)
        try:
            # Try to parse as numbers first
            selected = []
            for x in group.split(','):
                x = x.strip()
                if x.isdigit():
                    idx = int(x) - 1
                    if 0 <= idx < len(files):
                        selected.append(files[idx])
                    else:
                        print(f"Warning: Index {x} is out of range. Skipping.")
                else:
                    # If not a number, try to match filename
                    name = x.strip('"\'')
                    if not name.endswith('.txt'):
                        name += '.txt'
                    # Try exact match first
                    matching_files = [f for f in files if os.path.basename(f) == name]
                    if not matching_files:
                        # Try partial match
                        matching_files = [f for f in files if name in os.path.basename(f)]
                    if matching_files:
                        selected.extend(matching_files)
                    else:
                        print(f"Warning: No file found matching '{x}'. Skipping.")
            
            if selected:
                result.append(selected)
            else:
                print(f"Warning: No valid files found in group: {group}")
        except Exception as e:
            print(f"Error processing group '{group}': {str(e)}")
            continue
    
    return result if result else None

def find_common_part(strings):
    """Find any common part among a list of strings"""
    if not strings: return ""
    
    # First try to find common prefix
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix: break
    if prefix: return prefix
    
    # If no common prefix, try to find any common substring
    shortest = min(strings, key=len)
    for length in range(len(shortest), 0, -1):
        for start in range(len(shortest) - length + 1):
            candidate = shortest[start:start + length]
            if all(candidate in s for s in strings):
                return candidate
    return ""

def get_differing_parts(strings, common_part):
    """Get the parts that differ between strings"""
    if not common_part: return strings
    
    parts = []
    for s in strings:
        if common_part in s:
            before, after = s.split(common_part, 1)
            part = before + after
            if part: parts.append(part)
        else:
            parts.append(s)
    return parts

def split_filename(filename):
    """Split filename into prefix, middle, and suffix parts based on specific pattern"""
    # Remove extension
    base_name = os.path.splitext(os.path.basename(filename))[0]
    
    # Find the last underscore before the varying part
    parts = base_name.split('_')
    if len(parts) < 3:
        return base_name, "", ""
    
    # Try to find the common prefix (everything before the varying part)
    prefix_parts = []
    suffix_parts = []
    middle_part = ""
    
    # Look for common prefix pattern (e.g., "6v38_1_342_OPM_membrane_H2O_015_KCl")
    for i in range(len(parts)):
        if parts[i] in ['atena', 'gaia', 'venus']:  # Add more known middle parts if needed
            prefix_parts = parts[:i]
            middle_part = parts[i]
            suffix_parts = parts[i+1:]
            break
    
    if not prefix_parts:
        return base_name, "", ""
    
    prefix = '_'.join(prefix_parts)
    suffix = '_'.join(suffix_parts)
    
    return prefix, middle_part, suffix

def create_output_filename(files, plot_type, is_combined=False):
    """Create output filename based on input files and plot type"""
    if not files: return ""
    
    # Handle both single file and list of files
    if isinstance(files, list):
        if len(files) == 1 and not isinstance(files[0], list):
            base_name = os.path.splitext(os.path.basename(files[0]))[0]
            return f"{base_name}_{plot_type}.png"
        
        # For combined plots, get all file names
        all_files = []
        for group in files:
            if isinstance(group, list):
                all_files.extend(group)
            else:
                all_files.append(group)
        
        # Get base names without extension
        base_names = [os.path.splitext(os.path.basename(f))[0] for f in all_files]
        
        # Try to find common prefix
        common_prefix = os.path.commonprefix(base_names)
        if common_prefix and common_prefix[-1] == '_':
            common_prefix = common_prefix[:-1]
        
        # Get unique identifiers from each file
        unique_parts = []
        for name in base_names:
            # Remove common prefix if it exists
            if common_prefix:
                unique_part = name[len(common_prefix):].strip('_')
            else:
                unique_part = name
            
            # Get the first part before underscore or the whole name if no underscore
            first_part = unique_part.split('_')[0]
            if first_part and first_part not in unique_parts:
                unique_parts.append(first_part)
        
        # Create the filename
        if common_prefix:
            return f"{common_prefix}_{'_'.join(unique_parts)}_{plot_type}.png"
        else:
            return f"combined_{'_'.join(unique_parts)}_{plot_type}.png"
    else:
        # Single file case
        base_name = os.path.splitext(os.path.basename(files))[0]
        return f"{base_name}_{plot_type}.png"

def validate_file(file_path):
    """Validate file existence and content"""
    if not os.path.exists(file_path):
        raise DataError(f"File not found: {file_path}")
    
    if os.path.getsize(file_path) == 0:
        raise DataError(f"File is empty: {file_path}")
    
    return True

def read_data(file):
    """Read data from a file and return x, y values and last 20% points"""
    try:
        validate_file(file)
        
        x, y = [], []
        with open(file, 'r') as fp:
            lines = fp.readlines()
            if not lines:
                raise DataError(f"No data found in file: {file}")
            
            for line in lines:
                if 'nr_ramki' in line and 'ilosc_wody' in line:
                    try:
                        p = line.split(';')
                        x_val = int(p[0].split()[-1])
                        y_val = int(p[1].split(':')[-1].strip())
                        x.append(x_val)
                        y.append(y_val)
                    except (IndexError, ValueError) as e:
                        raise DataError(f"Invalid data format in file {file}: {str(e)}")
        
        if not x or not y:
            raise DataError(f"No valid data points found in file: {file}")
        
        y_np = np.array(y)
        n_points = len(y)
        if n_points < 5:
            raise DataError(f"Not enough data points in file {file} (minimum 5 required)")
        
        last_20_percent = round(n_points * 0.2)
        if last_20_percent < 1:
            raise DataError(f"Not enough data points for 20% calculation in file {file}")
        
        y_last = y_np[-last_20_percent:]
        return x, y, y_last, np.mean(y_last), np.std(y_last)
    
    except IOError as e:
        raise DataError(f"Error reading file {file}: {str(e)}")

def add_statistics_annotation(fig, avg, std, is_combined=False):
    """Add statistics annotation to the plot"""
    if is_combined:
        stats_text = f"Average of Averages: {np.mean(avg):.2f}<br>Average of Standard Deviations: {np.mean(std):.2f}"
    else:
        stats_text = f"Average: {avg[0]:.2f}<br>Standard Deviation: {std[0]:.2f}"
    
    fig.add_annotation(
        xref="paper", yref="paper", x=0.98, y=0.98,
        text=stats_text, showarrow=False, font=dict(size=TEXT_SIZE),
        align="right", bgcolor="rgba(0,0,0,0.0)", bordercolor="rgba(0,0,0,0.0)",
        borderwidth=1, borderpad=4
    )

def create_plot(files, out_file):
    """Create a plot from data files and save as PNG"""
    try:
        if not files:
            print("Error: No files provided for plotting")
            return
        
        # Get output directory from first file
        output_dir = os.path.dirname(files[0] if isinstance(files[0], str) else files[0][0])
        
        # Create single figures for all groups
        fig = go.Figure()
        violin_fig = go.Figure()
        
        # Process each group
        for group_idx, group in enumerate(files):
            if not group: continue
            
            # Store data and statistics for this group
            all_data = []
            all_avgs, all_stds = [], []
            valid_files = []
            
            # Process each file in the group
            for f in group:
                try:
                    if not os.path.exists(f):
                        print(f"Warning: File not found: {f}")
                        continue
                        
                    x, y, y_last, avg, std = read_data(f)
                    all_data.append((x, y, y_last))
                    all_avgs.append(avg)
                    all_stds.append(std)
                    valid_files.append(f)
                except DataError as e:
                    print(f"Warning: {str(e)} - Skipping file")
                    continue
            
            if not valid_files:
                print(f"Error: No valid files to plot in group {group_idx + 1}")
                continue
            
            # Create group name using the same logic as create_output_filename
            base_names = [os.path.splitext(os.path.basename(f))[0] for f in valid_files]
            common_prefix = os.path.commonprefix(base_names)
            if common_prefix and common_prefix[-1] == '_':
                common_prefix = common_prefix[:-1]
            
            unique_parts = []
            for name in base_names:
                if common_prefix:
                    unique_part = name[len(common_prefix):].strip('_')
                else:
                    unique_part = name
                first_part = unique_part.split('_')[0]
                if first_part and first_part not in unique_parts:
                    unique_parts.append(first_part)
            
            if common_prefix:
                group_name = f"{common_prefix}_{'_'.join(unique_parts)}"
            else:
                group_name = f"combined_{'_'.join(unique_parts)}"
            
            # Add scatter plot for this group
            if len(valid_files) > 1:
                # Average the data points
                x_avg = all_data[0][0]  # Use first file's x values
                y_avg = np.mean([d[1] for d in all_data], axis=0)
                fig.add_trace(go.Scatter(
                    x=x_avg, y=y_avg, mode='lines',
                    line=dict(width=1.5), name=group_name,
                    showlegend=True
                ))
            else:
                # Single file in group
                fig.add_trace(go.Scatter(
                    x=all_data[0][0], y=all_data[0][1], mode='lines',
                    line=dict(width=1.5), name=group_name,
                    showlegend=True
                ))
            
            # Add violin plot for this group
            if len(valid_files) > 1:
                # Combine all last 20% points for the group
                combined_last = np.concatenate([d[2] for d in all_data])
                violin_fig.add_trace(go.Violin(
                    y=combined_last, name=group_name, box_visible=True,
                    meanline_visible=True, showlegend=True,
                    line=dict(color=pio.templates['seaborn'].layout.colorway[group_idx % len(pio.templates['seaborn'].layout.colorway)]),
                    x0=group_idx
                ))
                
                # Add statistics annotation
                violin_fig.add_annotation(
                    xref="x", yref="y",
                    x=group_idx + 0.2, y=np.max(combined_last),
                    text=f"μ: {np.mean(combined_last):.2f}<br>σ: {np.std(combined_last):.2f}",
                    showarrow=False,
                    font=dict(size=TEXT_SIZE),
                    align="left",
                    bgcolor="rgba(0,0,0,0.0)",
                    bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1,
                    borderpad=4
                )
            else:
                # Single file in group
                violin_fig.add_trace(go.Violin(
                    y=all_data[0][2], name=group_name, box_visible=True,
                    meanline_visible=True, showlegend=True,
                    line=dict(color=pio.templates['seaborn'].layout.colorway[group_idx % len(pio.templates['seaborn'].layout.colorway)]),
                    x0=group_idx
                ))
                
                violin_fig.add_annotation(
                    xref="x", yref="y",
                    x=group_idx + 0.2, y=np.max(all_data[0][2]),
                    text=f"μ: {all_avgs[0]:.2f}<br>σ: {all_stds[0]:.2f}",
                    showarrow=False,
                    font=dict(size=TEXT_SIZE),
                    align="left",
                    bgcolor="rgba(0,0,0,0.0)",
                    bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1,
                    borderpad=4
                )
        
        # Update violin plot layout
        violin_fig.update_xaxes(range=[-0.5, len(files) - 0.5])
        violin_fig.update_layout(
            template='seaborn', margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                y=-0.1, x=0.5, font=dict(size=LEGEND_SIZE),
                xanchor='center', yanchor='top',
                bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)'
            ),
            xaxis=dict(
                title="20%", tickfont=dict(size=TEXT_SIZE),
                title_font=dict(size=TEXT_SIZE), showticklabels=False
            ),
            yaxis=dict(
                title="Number of water molecules",
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            )
        )
        
        # Update scatter plot layout
        fig.update_layout(
            template='seaborn', margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                y=-0.1, x=0.5, font=dict(size=LEGEND_SIZE),
                xanchor='center', yanchor='top',
                bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)'
            ),
            xaxis=dict(
                title="Time [ns]",
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            ),
            yaxis=dict(
                title="Number of water molecules",
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            )
        )
        
        # Create output filenames
        all_files = [f for group in files for f in group] if isinstance(files[0], list) else files
        scatter_out = create_output_filename(all_files, "scatter", True)
        violin_out = create_output_filename(all_files, "violin", True)
        
        scatter_out = os.path.join(output_dir, scatter_out)
        violin_out = os.path.join(output_dir, violin_out)
        
        # Save plots
        fig.write_image(scatter_out, width=1920, height=1440, scale=1)
        print(f'Created scatter plot: {scatter_out}')
        
        violin_fig.write_image(violin_out, width=1920, height=1440, scale=1)
        print(f'Created violin plot: {violin_out}')
    
    except Exception as e:
        print(f"Error in create_plot: {str(e)}")

def main():
    """Main program flow"""
    try:
        current_dir = os.getcwd()
        print(f"\nCurrent directory: {current_dir}")
        path = input("Enter data directory (press Enter to use current directory): ").strip()
        path = path or current_dir
        
        if not os.path.exists(path):
            print(f"Error: Directory '{path}' doesn't exist")
            return
        
        files = sorted([f for f in os.listdir(path) if f.endswith('.txt')])
        if not files:
            print(f"Error: No .txt files found in {path}")
            return
        
        filter_pattern = input("\nEnter filter (press Enter to proceed with all files): ").strip()
        if filter_pattern:
            files = [f for f in files if filter_pattern in f]
            if not files:
                print(f"Error: No files matching filter '{filter_pattern}' found")
                return
            print(f"\nFound {len(files)} files matching filter '{filter_pattern}'")
        
        print("\nCreating individual plots...")
        for f in files:
            try:
                full_path = os.path.join(path, f)
                create_plot([[full_path]], full_path)  # Note the double brackets
            except Exception as e:
                print(f"Error processing file {f}: {str(e)}")
        
        plot_counter = 1
        while True:
            sel = get_selection(files)
            if not sel: break
            
            try:
                # Convert file names to full paths
                selected_files = []
                for group in sel:
                    group_paths = [os.path.join(path, f) for f in group]
                    selected_files.append(group_paths)
                
                # Create a single plot with all groups
                create_plot(selected_files, os.path.join(path, f'combined_plot_{plot_counter}'))
                plot_counter += 1
            except Exception as e:
                print(f"Error creating combined plot: {str(e)}")
        
        print("\nGraph plotting completed!")
    
    except Exception as e:
        print(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()
