import os
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import scipy.stats

# Memory issue fix
pio.kaleido.scope.chromium_args = tuple([arg for arg in pio.kaleido.scope.chromium_args if arg != "--disable-dev-shm-usage"])

# Text size settings
TEXT_SIZE = 25
LEGEND_SIZE = TEXT_SIZE - 5

# Axis title settings
SCATTER_X_TITLE = "Time [ns]"
SCATTER_Y_TITLE = "Number of water molecules"
VIOLIN_X_TITLE = "20%"
VIOLIN_Y_TITLE = "Number of water molecules"

class DataError(Exception):
    """Custom exception for data-related errors"""
    pass

def get_selection(files, file_errors=None):
    """Let user select files for combined plot, displaying errors in red if present."""
    print("\nFiles:")
    for i, f in enumerate(files, 1):
        if file_errors and f in file_errors:
            print(f"{i}. {f} \033[91m({file_errors[f]})\033[0m")
        else:
            print(f"{i}. {f}")
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
            err_msg = str(e)
            if ':' in err_msg:
                err_msg = err_msg.split(':', 1)[0].strip()
            print(f"Error processing group '{group}': {err_msg}")
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

def find_varying_parts(files):
    """Find parts that vary between files by comparing their components"""
    if not files or len(files) == 1:
        return []
    
    # Split all filenames into parts
    all_parts = []
    for f in files:
        base_name = os.path.splitext(os.path.basename(f))[0]
        parts = base_name.split('_')
        all_parts.append(parts)
    
    # Find positions where parts differ
    varying_positions = set()
    for i in range(len(all_parts[0])):
        # Get all values at this position
        values = [parts[i] if i < len(parts) else None for parts in all_parts]
        # If any value is different from the first one, this position varies
        if len(set(values)) > 1:
            varying_positions.add(i)
    
    return sorted(list(varying_positions))

def split_filename(filename, varying_positions):
    """Split filename into parts based on varying positions"""
    # Remove extension
    base_name = os.path.splitext(os.path.basename(filename))[0]
    
    # Split by underscores
    parts = base_name.split('_')
    
    if not varying_positions:
        return base_name, [], ""
    
    # Split into prefix, varying parts, and suffix
    prefix = '_'.join(parts[:varying_positions[0]])
    varying_parts = [parts[i] for i in varying_positions if i < len(parts)]
    suffix = '_'.join(parts[varying_positions[-1] + 1:])
    
    return prefix, varying_parts, suffix

def get_group_name(files):
    """Generate a concise, non-redundant group name for a list of files."""
    if not files:
        return ""
    if len(files) == 1:
        return os.path.basename(files[0])
    
    # Get base names without extensions
    base_names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    
    # Find positions where parts vary
    varying_positions = find_varying_parts(base_names)
    
    # Split each filename into parts
    file_parts = []
    for name in base_names:
        prefix, varying, suffix = split_filename(name, varying_positions)
        file_parts.append((prefix, varying, suffix))
    
    # Find common prefix and suffix
    common_prefix = file_parts[0][0]
    common_suffix = file_parts[0][2]
    
    for prefix, _, suffix in file_parts[1:]:
        # Find common prefix
        while not prefix.startswith(common_prefix) and common_prefix:
            common_prefix = common_prefix.rsplit('_', 1)[0]
        
        # Find common suffix
        while not suffix.endswith(common_suffix) and common_suffix:
            common_suffix = common_suffix.split('_', 1)[1]
    
    # Collect all unique varying parts
    all_varying = set()
    for _, varying, _ in file_parts:
        all_varying.update(varying)
    
    # Build the final name
    parts = []
    if common_prefix:
        parts.append(common_prefix)
    
    if all_varying:
        # Sort varying parts to maintain consistent order
        sorted_varying = sorted(all_varying)
        # Join varying parts with underscore, without parentheses
        parts.append('_'.join(sorted_varying))
    
    if common_suffix:
        parts.append(common_suffix)
    
    return '_'.join(parts)

def create_output_filename(files, plot_type, is_combined=False):
    """Create output filename based on input files and plot type, eliminating redundancy."""
    if not files: return ""
    if isinstance(files, list):
        if len(files) == 1 and not isinstance(files[0], list):
            base_name = os.path.splitext(os.path.basename(files[0]))[0]
            return f"{base_name}_{plot_type}.png"
        all_files = []
        for group in files:
            if isinstance(group, list):
                all_files.extend(group)
            else:
                all_files.append(group)
        group_name = get_group_name(all_files)
        filename = f'{group_name}_{plot_type}.png'
        return filename
    else:
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
        is_distance = False
        with open(file, 'r') as fp:
            lines = fp.readlines()
            if not lines:
                raise DataError(f"No data found in file: {file}")
            
            for line in lines:
                # Split line by spaces and filter out empty strings
                parts = [p for p in line.split() if p]
                if len(parts) >= 4:  # Ensure we have at least 4 columns
                    try:
                        # Check if third column starts with 'distance'
                        if parts[2].lower().startswith('distance'):
                            is_distance = True
                        # Get second and fourth columns, strip non-numeric characters
                        x_val = float(''.join(c for c in parts[1] if c.isdigit() or c == '.' or c == '-'))
                        y_val = float(''.join(c for c in parts[3] if c.isdigit() or c == '.' or c == '-'))
                        x.append(x_val)
                        y.append(y_val)
                    except (IndexError, ValueError) as e:
                        raise DataError(f"Invalid data format in file {file}: {str(e)}")
        
        if not x or not y:
            raise DataError(f"No valid data points found in file: {file}")
        
        # Check if all values are zero
        if all(val == 0 for val in x):
            raise DataError("All x values are zero")
        
        if all(val == 0 for val in y):
            raise DataError("All y values are zero")
        
        y_np = np.array(y)
        n_points = len(y)
        if n_points < 5:
            raise DataError(f"Not enough data points in file {file} (minimum 5 required)")
        
        last_20_percent = round(n_points * 0.2)
        if last_20_percent < 1:
            raise DataError(f"Not enough data points for 20% calculation in file {file}")
        
        y_last = y_np[-last_20_percent:]
        return x, y, y_last, np.mean(y_last), np.std(y_last), is_distance
    
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

def create_plot(files, out_file, violin_names=None):
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
        
        # Track if we have any valid data to plot
        has_valid_data = False
        
        # For combined stats
        combined_avgs = []
        combined_stds = []
        
        # For singular stats
        singular_avg = None
        singular_std = None
        
        # Store colors for each violin
        violin_colors = []
        # Store y_last for each group for p-value calculation
        violin_y_last = []
        
        # Check if any file has distance data
        is_distance = False
        
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
                    x, y, y_last, avg, std, file_is_distance = read_data(f)
                    is_distance = is_distance or file_is_distance
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
            has_valid_data = True
            # For combined stats
            combined_avgs.extend(all_avgs)
            combined_stds.extend(all_stds)
            # For singular stats (if only one group and one file)
            if len(files) == 1 and len(valid_files) == 1:
                singular_avg = all_avgs[0]
                singular_std = all_stds[0]
            # Add scatter plot for this group
            if len(valid_files) > 1:
                x_avg = all_data[0][0]  # Use first file's x values
                y_avg = np.mean([d[1] for d in all_data], axis=0)
                group_name = get_group_name(valid_files)
                fig.add_trace(go.Scatter(
                    x=x_avg, y=y_avg, mode='lines',
                    line=dict(width=1.5), name=group_name,
                    showlegend=True
                ))
            else:
                group_name = get_group_name(valid_files)
                fig.add_trace(go.Scatter(
                    x=all_data[0][0], y=all_data[0][1], mode='lines',
                    line=dict(width=1.5), name=group_name,
                    showlegend=True
                ))
            # Add violin plot for this group
            if len(valid_files) > 1:
                combined_last = np.concatenate([d[2] for d in all_data])
                group_name = get_group_name(valid_files)
                color = pio.templates['seaborn'].layout.colorway[group_idx % len(pio.templates['seaborn'].layout.colorway)]
                violin_colors.append(color)
                violin_y_last.append(combined_last)
                violin_fig.add_trace(go.Violin(
                    y=combined_last, name=group_name, box_visible=True,
                    meanline_visible=True, showlegend=True,
                    line=dict(color=color),
                    x0=group_idx
                ))
                violin_fig.add_annotation(
                    xref="x", yref="y",
                    x=group_idx + 0.3, y=np.max(combined_last),
                    text=f"<span style='color:{color}'>μ: {np.mean(combined_last):.2f}<br>σ: {np.std(combined_last):.2f}</span>",
                    showarrow=False,
                    font=dict(size=TEXT_SIZE),
                    align="left",
                    bgcolor="rgba(0,0,0,0.0)",
                    bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1,
                    borderpad=4
                )
            else:
                group_name = get_group_name(valid_files)
                color = pio.templates['seaborn'].layout.colorway[group_idx % len(pio.templates['seaborn'].layout.colorway)]
                violin_colors.append(color)
                violin_y_last.append(all_data[0][2])
                violin_fig.add_trace(go.Violin(
                    y=all_data[0][2], name=group_name, box_visible=True,
                    meanline_visible=True, showlegend=True,
                    line=dict(color=color),
                    x0=group_idx
                ))
                violin_fig.add_annotation(
                    xref="x", yref="y",
                    x=group_idx + 0.3, y=np.max(all_data[0][2]),
                    text=f"<span style='color:{color}'>μ: {all_avgs[0]:.2f}<br>σ: {all_stds[0]:.2f}</span>",
                    showarrow=False,
                    font=dict(size=TEXT_SIZE),
                    align="left",
                    bgcolor="rgba(0,0,0,0.0)",
                    bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1,
                    borderpad=4
                )
        if not has_valid_data:
            print("Error: No valid data to plot. Skipping graph creation.")
            return
        is_combined = (isinstance(files, list) and (len(files) > 1 or (len(files) == 1 and len(files[0]) > 1)))
        if is_combined and combined_avgs and combined_stds:
            stats_text = f"Average of Averages: {np.mean(combined_avgs):.2f}<br>Average of Standard Deviations: {np.mean(combined_stds):.2f}"
            for plot in [fig, violin_fig]:
                plot.add_annotation(
                    xref="paper", yref="paper", x=0.98, y=0.98,
                    text=stats_text, showarrow=False, font=dict(size=TEXT_SIZE, color="black"),
                    align="right", bgcolor="rgba(0,0,0,0.0)", bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1, borderpad=4
                )
        if not is_combined and singular_avg is not None and singular_std is not None:
            stats_text = f"Average: {singular_avg:.2f}<br>Standard Deviation: {singular_std:.2f}"
            for plot in [fig, violin_fig]:
                plot.add_annotation(
                    xref="paper", yref="paper", x=0.98, y=0.98,
                    text=stats_text, showarrow=False, font=dict(size=TEXT_SIZE, color="black"),
                    align="right", bgcolor="rgba(0,0,0,0.0)", bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=1, borderpad=4
                )
        # After all violins are added, find the highest data point for y-axis range
        all_violin_y = []
        for trace in violin_fig.data:
            if hasattr(trace, 'y'):
                all_violin_y.extend(trace.y)
        is_combined_violin = (isinstance(files, list) and (len(files) > 1 or (len(files) == 1 and len(files[0]) > 1)))
        if all_violin_y and is_combined_violin:
            max_y = max(all_violin_y)
            min_y = min(all_violin_y)
            if is_distance:
                yaxis_range = [max(0, min_y - min_y * 0.05), max_y + max_y * 0.05]
            else:
                yaxis_range = [max(0, min_y - 20), max_y + 25]
        else:
            yaxis_range = None

        # Update violin plot layout
        violin_fig.update_xaxes(range=[-0.5, len(files) - 0.5])
        
        # Create colored tick labels
        ticktext = violin_names if violin_names else [str(i+1) for i in range(len(files))]
        colored_ticktext = [f'<span style="color:{color}">{text}</span>' for color, text in zip(violin_colors, ticktext)]
        
        # Update scatter plot layout
        y_title = "Distance [Å]" if is_distance else SCATTER_Y_TITLE
        fig.update_layout(
            template='seaborn', margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                y=-0.1, x=0.5, font=dict(size=LEGEND_SIZE),
                xanchor='center', yanchor='top',
                bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)'
            ),
            xaxis=dict(
                title=SCATTER_X_TITLE,
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            ),
            yaxis=dict(
                title=y_title,
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            )
        )
        
        # Update violin plot layout
        violin_layout_kwargs = dict(
            template='seaborn', margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                y=-0.1, x=0.5, font=dict(size=LEGEND_SIZE),
                xanchor='center', yanchor='top',
                bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)'
            ),
            xaxis=dict(
                title="", tickfont=dict(size=TEXT_SIZE),
                title_font=dict(size=TEXT_SIZE), showticklabels=True,
                ticktext=colored_ticktext,
                tickvals=list(range(len(files)))
            ),
            yaxis=dict(
                title=y_title,
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            )
        )
        if yaxis_range:
            violin_layout_kwargs['yaxis']['range'] = yaxis_range
        violin_fig.update_layout(**violin_layout_kwargs)

        # --- P-VALUE ANNOTATIONS BETWEEN VIOLINS ---
        # Only if there are at least 2 violins
        if len(violin_y_last) > 1:
            for i in range(len(violin_y_last) - 1):
                y1 = violin_y_last[i]
                y2 = violin_y_last[i+1]
                # T-test
                t_stat, p_val = scipy.stats.ttest_ind(y1, y2, equal_var=False)
                # Color: red if significant, else black; both 70% transparent
                if p_val < 0.05:
                    color = 'rgba(255,0,0,0.7)'
                else:
                    color = 'rgba(0,0,0,0.7)'
                # Add p-value and t-value text below the graph
                violin_fig.add_annotation(
                    xref="paper", yref="paper",
                    x=(i + 0.5) / (len(files) - 1), y=-0.1,
                    text=f"p = {p_val:.2g}<br>t = {t_stat:.2f}",
                    showarrow=False,
                    font=dict(size=TEXT_SIZE, color=color),
                    align="center",
                    bgcolor="rgba(0,0,0,0.0)",
                    bordercolor="rgba(0,0,0,0.0)",
                    borderwidth=0,
                    borderpad=2
                )
        # --- END P-VALUE ANNOTATIONS ---

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

def process_selection(selection, files, file_errors):
    """Process selection string and return groups of files and their names"""
    if not selection: return None, None
    if selection.lower() == 'all': return [files], None  # Return as a single group
    
    # Split by semicolon first to get groups
    groups = [g.strip() for g in selection.split(';')]
    result = []
    
    # Ask for violin names if there are multiple groups
    violin_names = None
    if len(groups) > 1:
        name_input = input("\nEnter names for violins (comma-separated, press Enter to use default numbers): ").strip()
        if name_input:
            violin_names = [name.strip() for name in name_input.split(',')]
            if len(violin_names) != len(groups):
                print(f"Warning: Number of names ({len(violin_names)}) doesn't match number of groups ({len(groups)}). Using default numbers.")
                violin_names = None
    
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
            err_msg = str(e)
            if ':' in err_msg:
                err_msg = err_msg.split(':', 1)[0].strip()
            print(f"Error processing group '{group}': {err_msg}")
            continue
    
    return (result if result else None), violin_names

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
        
        # Pre-validate all files and collect errors
        file_errors = {}
        all_files = sorted([f for f in os.listdir(path) if f.endswith('.txt')])
        if not all_files:
            print(f"Error: No .txt files found in {path}")
            return
        
        for f in all_files:
            full_path = os.path.join(path, f)
            try:
                validate_file(full_path)
                read_data(full_path)
            except DataError as e:
                err_msg = str(e)
                if ':' in err_msg:
                    err_msg = err_msg.split(':', 1)[0].strip()
                file_errors[f] = err_msg
            except Exception as e:
                err_msg = str(e)
                if ':' in err_msg:
                    err_msg = err_msg.split(':', 1)[0].strip()
                file_errors[f] = err_msg
        
        # Start with all files
        current_files = all_files
        plot_counter = 1
        
        while True:
            # Display current files
            print("\nFiles:")
            for i, f in enumerate(current_files, 1):
                if f in file_errors:
                    print(f"{i}. {f} \033[91m({file_errors[f]})\033[0m")
                else:
                    print(f"{i}. {f}")
            
            # Get user input
            user_input = input("\nEnter filter, 'all', 'back', 'exit', or file selection (numbers/names with , or ;): ").strip()
            
            if not user_input or user_input.lower() == 'exit':
                break
            
            if user_input.lower() == 'back':
                current_files = all_files
                continue
            
            if user_input.lower() == 'all':
                # Create individual plots for all current files
                print("\nCreating individual plots...")
                for f in current_files:
                    if f in file_errors:
                        print(f"Skipping {f} due to error: {file_errors[f]}")
                        continue
                    try:
                        full_path = os.path.join(path, f)
                        create_plot([[full_path]], full_path)
                    except Exception as e:
                        print(f"Error processing file {f}: {str(e)}")
                continue
            
            # Check if input is a single number
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(current_files):
                    f = current_files[idx]
                    if f in file_errors:
                        print(f"Skipping {f} due to error: {file_errors[f]}")
                        continue
                    try:
                        full_path = os.path.join(path, f)
                        create_plot([[full_path]], full_path)
                    except Exception as e:
                        print(f"Error processing file {f}: {str(e)}")
                else:
                    print(f"Warning: Index {user_input} is out of range.")
                continue
            
            # Check if input contains commas or semicolons
            if ',' in user_input or ';' in user_input:
                # Process selection directly
                sel, violin_names = process_selection(user_input, current_files, file_errors)
                if sel:
                    try:
                        # Convert file names to full paths, but skip files with errors
                        selected_files = []
                        for group in sel:
                            group_paths = []
                            for f in group:
                                if f in file_errors:
                                    print(f"Skipping {f} due to error: {file_errors[f]}")
                                    continue
                                group_paths.append(os.path.join(path, f))
                            if group_paths:
                                selected_files.append(group_paths)
                        if selected_files:
                            create_plot(selected_files, os.path.join(path, f'combined_plot_{plot_counter}'), violin_names)
                            plot_counter += 1
                    except Exception as e:
                        print(f"Error creating combined plot: {str(e)}")
                continue
            
            # Remove asterisks from filter input
            filter_input = user_input.replace('*', '')
            
            # Treat as filter
            filtered_files = [f for f in current_files if filter_input in f]
            if not filtered_files:
                print(f"No files matching filter '{filter_input}' found")
                continue
            current_files = filtered_files
        
        print("\nGraph plotting completed!")
    
    except Exception as e:
        err_msg = str(e)
        if ':' in err_msg:
            err_msg = err_msg.split(':', 1)[0].strip()
        print(f"Fatal error: {err_msg}")

if __name__ == "__main__":
    main()