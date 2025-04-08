import os
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
# Memory issue fix
pio.kaleido.scope.chromium_args = tuple([arg for arg in pio.kaleido.scope.chromium_args if arg != "--disable-dev-shm-usage"])

def get_selection(files):
    """Let user select files for combined plot"""
    # Show numbered list of available files
    print("\nFiles:", *[f"{i}. {f}" for i, f in enumerate(files, 1)], sep='\n')
    
    # Get user input
    sel = input("\nEnter number or name separated by coma. Press enter to finish: ").strip()
    if not sel: return None  # Skip if empty input
    if sel.lower() == 'all': return files  # Return all files if 'all' selected
    
    # Try to get files by numbers
    try: return [files[int(x)-1] for x in sel.split(',')]
    except:
        # If numbers fail, try to match by filenames
        names = [n.strip().strip('"\'') + ('' if n.endswith('.txt') else '.txt') for n in sel.split(',')]
        return [f for f in files if f in names] or print("No matches. Try again.")

def find_common_prefix(strings):
    """Find the longest common prefix among a list of strings"""
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix

def create_plot(files, out_file):
    """Create a plot from data files and save as PNG"""
    fig = go.Figure()
    
    # Find common prefix in filenames for combined plot
    if len(files) > 1:
        common_prefix = find_common_prefix([os.path.splitext(os.path.basename(f))[0] for f in files])
    else:
        common_prefix = ""
    
    # Store statistics for combined plot
    all_avgs = []
    all_stds = []
    
    # Read data from each file
    for f in files:
        x, y = [], []  # Store frame numbers and water counts
        with open(f, 'r') as fp:
            for line in fp:
                if 'nr_ramki' in line and 'ilosc_wody' in line:
                    p = line.split(';')
                    x.append(int(p[0].split()[-1]))  # Get frame number
                    y.append(int(p[1].split(':')[-1].strip()))  # Get water count
        
        # Add line plot for this file
        if x and y:
            # Convert to numpy arrays for calculations
            y_np = np.array(y)
            
            # Calculate last 20% of points
            n_points = len(y)
            last_20_percent = round(n_points * 0.2)
            y_last = y_np[-last_20_percent:]
            
            # Calculate statistics for last 20%
            avg = np.mean(y_last)
            std = np.std(y_last)
            
            # Store statistics for combined plot
            all_avgs.append(avg)
            all_stds.append(std)
            
            # Get filename for legend
            filename = os.path.splitext(os.path.basename(f))[0]
            if common_prefix and len(files) > 1:
                # Remove common prefix for combined plot
                legend_name = filename[len(common_prefix):] or filename
            else:
                legend_name = filename
            
            # Add original data plot
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(width=1.5),
                                   name=legend_name, showlegend=True))
    
    # Add statistics annotation
    if len(files) > 1:
        # For combined plot, show average of averages and average of standard deviations
        avg_of_avgs = np.mean(all_avgs)
        avg_of_stds = np.mean(all_stds)
        stats_text = f"Average of Averages: {avg_of_avgs:.2f}<br>Average of Standard Deviations: {avg_of_stds:.2f}" #-------------------------------- Here change text of average of averages and average of standard deviations
    else:
        # For single plot, show individual statistics
        stats_text = f"Average: {all_avgs[0]:.2f}<br>Standard Deviation: {all_stds[0]:.2f}" #-------------------------------- Here change text of average and standard deviation
    
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.98, y=0.98,  # Top right corner
        text=stats_text,
        showarrow=False,
        font=dict(size=25), #-------------------------------- Here change font size of average and standard deviation
        align="right",
        bgcolor="rgba(0,0,0,0.0)",
        bordercolor="rgba(0,0,0,0.0)",
        borderwidth=1,
        borderpad=4
    )
    
    # Customize and save plot if we have data
    if fig.data:
        # Get axis labels from user
        x_label = "Time [ns]" #-------------------------------- Here change x axis label
        y_label = "Number of water molecules" #-------------------------------- Here change y axis label
        
        fig.update_layout(
            template='seaborn',  # Use seaborn style
            margin=dict(l=20, r=20, t=20, b=20),  # Small margins
            
            # Legend settings
            legend=dict(
                y=-0.1,  # Position below the plot
                x=0.5,   # Center horizontally
                font=dict(size=20),  # Large text ----------------------------Here change legend font size
                xanchor='center',  # Center the legend
                yanchor='top',     # Anchor to top of legend
                bgcolor='rgba(0,0,0,0)',  # Transparent background
                bordercolor='rgba(0,0,0,0)'  # Transparent border
            ),
            
            # Axis settings
            xaxis=dict(
                title=x_label,  # Custom X-axis label
                tickfont=dict(size=25), #-------------------------------- Here change x axis font size
                title_font=dict(size=25) #-------------------------------- Here change x axis font size
            ),
            yaxis=dict(
                title=y_label,  # Custom Y-axis label
                tickfont=dict(size=25), #-------------------------------- Here change y axis font size
                title_font=dict(size=25) #-------------------------------- Here change y axis font size
            )
        )
        
        # Save high-quality PNG
        fig.write_image(out_file, width=1920, height=1440, scale=1)
        print(f'Created: {out_file}')

def main():
    """Main program flow"""
    # Show current directory and get input
    current_dir = os.getcwd()
    print(f"\nCurrent directory: {current_dir}")
    path = input("Enter data directory (press Enter to use current directory): ").strip()
    
    # Use current directory if input is empty
    if not path:
        path = current_dir
    
    if not os.path.exists(path): return print(f"Directory '{path}' doesn't exist")
    
    # Find all .txt files
    files = sorted([f for f in os.listdir(path) if f.endswith('.txt')])
    if not files: return print(f"No .txt files in {path}")
    
    # Ask for filter
    filter_pattern = input("\nEnter filter (press Enter to proceed with all files): ").strip()
    if filter_pattern:
        filtered_files = [f for f in files if filter_pattern in f]
        if not filtered_files:
            return print(f"No files matching filter '{filter_pattern}' found")
        files = filtered_files
        print(f"\nFound {len(files)} files matching filter '{filter_pattern}'")
    
    # Create individual plots
    print("\nCreating individual plots...")
    for f in files:
        create_plot([os.path.join(path, f)], os.path.splitext(os.path.join(path, f))[0] + '_plot.png')
    
    # Create combined plot if requested
    sel = get_selection(files)
    if sel:
        out = os.path.join(path, '-'.join(os.path.splitext(f)[0] for f in sel) + '_plot.png')
        create_plot([os.path.join(path, f) for f in sel], out)
    
    print("\nAll graphs plotted successfully!")

# Run the program
main()
