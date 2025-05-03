import os
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

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

def get_group_name(files):
    """Generate a concise, non-redundant group name for a list of files, similar to create_output_filename logic."""
    if not files:
        return ""
    if len(files) == 1:
        return os.path.basename(files[0])
    base_names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    def get_common_prefix(names):
        if not names: return ''
        prefix = names[0]
        for name in names[1:]:
            while not name.startswith(prefix) and prefix:
                prefix = prefix[:-1]
        return prefix
    common_prefix = get_common_prefix(base_names)
    if common_prefix and common_prefix[-1] == '_':
        common_prefix = common_prefix[:-1]
    stripped = [name[len(common_prefix):] if name.startswith(common_prefix) else name for name in base_names]
    stripped = [s[1:] if s.startswith('_') else s for s in stripped]
    def get_common_suffix(names):
        if not names: return ''
        rev = [name[::-1] for name in names]
        suffix = rev[0]
        for name in rev[1:]:
            while not name.startswith(suffix) and suffix:
                suffix = suffix[:-1]
        return suffix[::-1]
    common_suffix = get_common_suffix(stripped)
    if common_suffix and common_suffix[0] == '_':
        common_suffix = common_suffix[1:]
    unique_middles = []
    for s in stripped:
        if common_suffix and s.endswith(common_suffix):
            middle = s[:-(len(common_suffix))]
            if middle.endswith('_'):
                middle = middle[:-1]
        else:
            middle = s
        unique_middles.append(middle)
    unique_middles = [m for m in unique_middles if m]
    parts = []
    if common_prefix:
        parts.append(common_prefix)
    if unique_middles:
        parts.append('_'.join(unique_middles))
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
        
        # Track if we have any valid data to plot
        has_valid_data = False
        
        # For combined stats
        combined_avgs = []
        combined_stds = []
        
        # For singular stats
        singular_avg = None
        singular_std = None
        
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
            yaxis_range = [max(0, min_y - 20), max_y + 25]
        else:
            yaxis_range = None

        # Update violin plot layout
        violin_fig.update_xaxes(range=[-0.5, len(files) - 0.5])
        violin_layout_kwargs = dict(
            template='seaborn', margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                y=-0.1, x=0.5, font=dict(size=LEGEND_SIZE),
                xanchor='center', yanchor='top',
                bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)'
            ),
            xaxis=dict(
                title=VIOLIN_X_TITLE, tickfont=dict(size=TEXT_SIZE),
                title_font=dict(size=TEXT_SIZE), showticklabels=False
            ),
            yaxis=dict(
                title=VIOLIN_Y_TITLE,
                tickfont=dict(size=TEXT_SIZE), title_font=dict(size=TEXT_SIZE)
            )
        )
        if yaxis_range:
            violin_layout_kwargs['yaxis']['range'] = yaxis_range
        violin_fig.update_layout(**violin_layout_kwargs)
        # Update scatter plot layout
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
                title=SCATTER_Y_TITLE,
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
        
        # Pre-validate all files and collect errors before filtering/graphing
        file_errors = {}
        for f in files:
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
        
        # Print all files with errors in red if any, before filtering
        print("\nFiles (before filtering):")
        for i, f in enumerate(files, 1):
            if f in file_errors:
                print(f"{i}. {f} \033[91m({file_errors[f]})\033[0m")
            else:
                print(f"{i}. {f}")
        
        filter_pattern = input("\nEnter filter (press Enter to proceed with all files): ").strip()
        if filter_pattern:
            files = [f for f in files if filter_pattern in f]
            if not files:
                print(f"Error: No files matching filter '{filter_pattern}' found")
                return
            print(f"\nFound {len(files)} files matching filter '{filter_pattern}'")
        
        print("\nCreating individual plots...")
        for f in files:
            if f in file_errors:
                print(f"Skipping {f} due to error: {file_errors[f]}")
                continue
            try:
                full_path = os.path.join(path, f)
                create_plot([[full_path]], full_path)  # Note the double brackets
            except DataError as e:
                err_msg = str(e)
                if ':' in err_msg:
                    err_msg = err_msg.split(':', 1)[0].strip()
                file_errors[f] = err_msg
                print(f"Error processing file {f}: {err_msg}")
            except Exception as e:
                err_msg = str(e)
                if ':' in err_msg:
                    err_msg = err_msg.split(':', 1)[0].strip()
                file_errors[f] = err_msg
                print(f"Error processing file {f}: {err_msg}")
        
        plot_counter = 1
        while True:
            sel = get_selection(files, file_errors)
            if not sel: break
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
                if not selected_files:
                    print("No valid files selected for plotting.")
                    continue
                # Create a single plot with all groups
                create_plot(selected_files, os.path.join(path, f'combined_plot_{plot_counter}'))
                plot_counter += 1
            except Exception as e:
                err_msg = str(e)
                if ':' in err_msg:
                    err_msg = err_msg.split(':', 1)[0].strip()
                print(f"Error creating combined plot: {err_msg}")
        
        print("\nGraph plotting completed!")
    
    except Exception as e:
        err_msg = str(e)
        if ':' in err_msg:
            err_msg = err_msg.split(':', 1)[0].strip()
        print(f"Fatal error: {err_msg}")

if __name__ == "__main__":
    main()
