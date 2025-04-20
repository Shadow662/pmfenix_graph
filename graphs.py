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
    sel = input("\nEnter number or name separated by coma. Press enter to finish: ").strip()
    if not sel: return None
    if sel.lower() == 'all': return files
    
    try: return [files[int(x)-1] for x in sel.split(',')]
    except:
        names = [n.strip().strip('"\'') + ('' if n.endswith('.txt') else '.txt') for n in sel.split(',')]
        return [f for f in files if f in names] or print("No matches. Try again.")

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

def create_output_filename(files, plot_type, is_combined=False):
    """Create output filename based on input files and plot type"""
    if not files: return ""
    
    base_names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    
    if len(files) == 1:
        return f"{base_names[0]}_{plot_type}.png"
    
    common_part = find_common_part(base_names)
    differing_parts = get_differing_parts(base_names, common_part)
    
    # Clean up differing parts
    cleaned_parts = []
    for part in differing_parts:
        cleaned = ''.join(c for c in part if c.isalnum() or c == '-')
        if cleaned: cleaned_parts.append(cleaned)
    
    if not cleaned_parts:
        cleaned_parts = [str(i) for i in range(len(files))]
    
    if common_part:
        return f"combined_plot_{common_part}_{'-'.join(cleaned_parts)}_{plot_type}.png"
    return f"combined_plot_{'-'.join(cleaned_parts)}_{plot_type}.png"

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
        
        scatter_out = create_output_filename(files, "scatter", len(files) > 1)
        if not scatter_out:
            print("Error: Could not generate output filename")
            return
        
        output_dir = os.path.dirname(files[0])
        scatter_out = os.path.join(output_dir, scatter_out)
        
        fig = go.Figure()
        violin_fig = go.Figure()
        
        # Store data and statistics
        all_data = []
        all_avgs, all_stds = [], []
        valid_files = []
        
        # Process each file
        for f in files:
            try:
                x, y, y_last, avg, std = read_data(f)
                all_data.append((x, y, y_last))
                all_avgs.append(avg)
                all_stds.append(std)
                valid_files.append(f)
                
                filename = os.path.splitext(os.path.basename(f))[0]
                fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(width=1.5),
                                       name=filename, showlegend=True))
            except DataError as e:
                print(f"Warning: {str(e)} - Skipping file")
                continue
        
        if not valid_files:
            print("Error: No valid files to plot")
            return
        
        # Create violin plot
        if all_data:
            try:
                if len(valid_files) > 1:
                    default_colors = pio.templates['seaborn'].layout.colorway
                    
                    for i, (_, _, y_last) in enumerate(all_data):
                        filename = os.path.splitext(os.path.basename(valid_files[i]))[0]
                        color = default_colors[i % len(default_colors)]
                        
                        violin_fig.add_trace(go.Violin(
                            y=y_last, name=filename, box_visible=True,
                            meanline_visible=True, showlegend=True,
                            line=dict(color=color), x0=i
                        ))
                        
                        violin_fig.add_annotation(
                            xref="x", yref="y",
                            x=i + 0.2, y=np.max(y_last),
                            text=f"μ: {all_avgs[i]:.2f}<br>σ: {all_stds[i]:.2f}",
                            showarrow=False,
                            font=dict(size=TEXT_SIZE, color=color),
                            align="left",
                            bgcolor="rgba(0,0,0,0.0)",
                            bordercolor="rgba(0,0,0,0.0)",
                            borderwidth=1,
                            borderpad=4
                        )
                    
                    violin_fig.update_xaxes(range=[-0.5, len(valid_files) - 0.5])
                else:
                    filename = os.path.splitext(os.path.basename(valid_files[0]))[0]
                    violin_fig.add_trace(go.Violin(
                        y=all_data[0][2], name=filename, box_visible=True,
                        meanline_visible=True, showlegend=True
                    ))
                    
                    add_statistics_annotation(violin_fig, all_avgs, all_stds)
                
                # Customize violin plot
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
                
                violin_out = create_output_filename(valid_files, "violin", len(valid_files) > 1)
                violin_out = os.path.join(output_dir, violin_out)
                violin_fig.write_image(violin_out, width=1920, height=1440, scale=1)
                print(f'Created violin plot: {violin_out}')
            except Exception as e:
                print(f"Error creating violin plot: {str(e)}")
        
        # Add statistics to main plot
        add_statistics_annotation(fig, all_avgs, all_stds, len(valid_files) > 1)
        
        # Customize and save main plot
        if fig.data:
            try:
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
                
                fig.write_image(scatter_out, width=1920, height=1440, scale=1)
                print(f'Created scatter plot: {scatter_out}')
            except Exception as e:
                print(f"Error creating scatter plot: {str(e)}")
    
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
                create_plot([os.path.join(path, f)], os.path.join(path, f))
            except Exception as e:
                print(f"Error processing file {f}: {str(e)}")
        
        plot_counter = 1
        while True:
            sel = get_selection(files)
            if not sel: break
            
            try:
                selected_files = [os.path.join(path, f) for f in sel]
                temp_out = os.path.join(path, f'combined_plot_{plot_counter}')
                create_plot(selected_files, temp_out)
                plot_counter += 1
            except Exception as e:
                print(f"Error creating combined plot: {str(e)}")
        
        print("\nGraph plotting completed!")
    
    except Exception as e:
        print(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()
