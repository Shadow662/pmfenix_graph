import os
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
# Memory issue fix
pio.kaleido.scope.chromium_args = tuple([arg for arg in pio.kaleido.scope.chromium_args if arg != "--disable-dev-shm-usage"])

# Text size settings
TEXT_SIZE = 25  #-------------------------------- Here change text size for all graphs

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
    violin_fig = go.Figure()  # Create a separate figure for violin plot
    
    # Find common prefix in filenames for combined plot
    if len(files) > 1:
        common_prefix = find_common_prefix([os.path.splitext(os.path.basename(f))[0] for f in files])
    else:
        common_prefix = ""
    
    # Store statistics for combined plot
    all_avgs = []
    all_stds = []
    all_last_20_percent = []  # Store all last 20% points for violin plot
    
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
            
            # Store last 20% points for violin plot
            all_last_20_percent.append(y_last)
            
            # Calculate statistics for last 20%
            avg = np.mean(y_last)
            std = np.std(y_last)
            
            # Store statistics for combined plot
            all_avgs.append(avg)
            all_stds.append(std)
            
            # Get filename for legend - use full filename
            filename = os.path.splitext(os.path.basename(f))[0]
            
            # Add original data plot with full filename in legend
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(width=1.5),
                                   name=filename, showlegend=True))
    
    # Create violin plot
    if all_last_20_percent:  # Only create violin plot if we have data
        if len(files) > 1:
            # For combined plot, show each file's last 20% points separately
            for i, (f, y_last) in enumerate(zip(files, all_last_20_percent)):
                filename = os.path.splitext(os.path.basename(f))[0]
                violin_fig.add_trace(go.Violin(
                    y=y_last,
                    name=filename,  # Use actual filename in legend
                    box_visible=True,
                    meanline_visible=True,
                    showlegend=True
                ))
        else:
            # For single plot, show individual violin with actual filename
            filename = os.path.splitext(os.path.basename(files[0]))[0]
            violin_fig.add_trace(go.Violin(
                y=all_last_20_percent[0],
                name=filename,  # Use actual filename in legend
                box_visible=True,
                meanline_visible=True,
                showlegend=True
            ))
        
        # Add statistics to violin plot
        if len(files) > 1 and all_avgs and all_stds:
            # For combined plot, show average of averages and average of standard deviations
            avg_of_avgs = np.mean(all_avgs)
            avg_of_stds = np.mean(all_stds)
            violin_stats_text = f"Average of Averages: {avg_of_avgs:.2f}<br>Average of Standard Deviations: {avg_of_stds:.2f}"
        elif all_avgs and all_stds:
            # For single plot, show individual statistics
            violin_stats_text = f"Average: {all_avgs[0]:.2f}<br>Standard Deviation: {all_stds[0]:.2f}"
        else:
            violin_stats_text = "No valid data points found"
        
        violin_fig.add_annotation(
            xref="paper", yref="paper",
            x=0.98, y=0.98,  # Top right corner
            text=violin_stats_text,
            showarrow=False,
            font=dict(size=TEXT_SIZE),
            align="right",
            bgcolor="rgba(0,0,0,0.0)",
            bordercolor="rgba(0,0,0,0.0)",
            borderwidth=1,
            borderpad=4
        )
        
        # Customize violin plot
        violin_fig.update_layout(
            template='seaborn',  # Use seaborn style
            margin=dict(l=20, r=20, t=20, b=20),  # Small margins
            
            # Legend settings
            legend=dict(
                y=-0.1,  # Position below the plot
                x=0.5,   # Center horizontally
                font=dict(size=TEXT_SIZE-5),  # Slightly smaller than main text
                xanchor='center',  # Center the legend
                yanchor='top',     # Anchor to top of legend
                bgcolor='rgba(0,0,0,0)',  # Transparent background
                bordercolor='rgba(0,0,0,0)'  # Transparent border
            ),
            
            xaxis=dict(
                title="20%",  # X-axis label
                tickfont=dict(size=TEXT_SIZE),
                title_font=dict(size=TEXT_SIZE),
                showticklabels=False  # Hide tick labels
            ),
            
            yaxis=dict(
                title="Number of water molecules",  # Y-axis label
                tickfont=dict(size=TEXT_SIZE),
                title_font=dict(size=TEXT_SIZE)
            )
        )
        
        # Save violin plot
        violin_out_file = os.path.splitext(out_file)[0] + '_violin.png'
        violin_fig.write_image(violin_out_file, width=1920, height=1440, scale=1)
        print(f'Created: {violin_out_file}')
    
    # Add statistics annotation
    if len(files) > 1 and all_avgs and all_stds:
        # For combined plot, show average of averages and average of standard deviations
        avg_of_avgs = np.mean(all_avgs)
        avg_of_stds = np.mean(all_stds)
        stats_text = f"Average of Averages: {avg_of_avgs:.2f}<br>Average of Standard Deviations: {avg_of_stds:.2f}" #-------------------------------- Here change text of average of averages and average of standard deviations
    elif all_avgs and all_stds:
        # For single plot, show individual statistics
        stats_text = f"Average: {all_avgs[0]:.2f}<br>Standard Deviation: {all_stds[0]:.2f}" #-------------------------------- Here change text of average and standard deviation
    else:
        stats_text = "No valid data points found"
    
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.98, y=0.98,  # Top right corner
        text=stats_text,
        showarrow=False,
        font=dict(size=TEXT_SIZE), #-------------------------------- Here change font size of average and standard deviation
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
                font=dict(size=TEXT_SIZE-5),  # Slightly smaller than main text ----------------------------Here change legend font size
                xanchor='center',  # Center the legend
                yanchor='top',     # Anchor to top of legend
                bgcolor='rgba(0,0,0,0)',  # Transparent background
                bordercolor='rgba(0,0,0,0)'  # Transparent border
            ),
            
            # Axis settings
            xaxis=dict(
                title=x_label,  # Custom X-axis label
                tickfont=dict(size=TEXT_SIZE), #-------------------------------- Here change x axis font size
                title_font=dict(size=TEXT_SIZE) #-------------------------------- Here change x axis font size
            ),
            yaxis=dict(
                title=y_label,  # Custom Y-axis label
                tickfont=dict(size=TEXT_SIZE), #-------------------------------- Here change y axis font size
                title_font=dict(size=TEXT_SIZE) #-------------------------------- Here change y axis font size
            )
        )
        
        # Save high-quality PNGs
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
    
    # Create combined plots in a loop
    plot_counter = 1
    while True:
        sel = get_selection(files)
        if not sel:
            break  # Exit if user presses Enter without selection
            
        # Find common prefix for output filename
        if len(sel) > 1:
            common_prefix = find_common_prefix([os.path.splitext(f)[0] for f in sel])
            # Create output filename with common prefix removed
            out = os.path.join(path, f'combined_plot_{plot_counter}_{common_prefix}.png')
        else:
            out = os.path.join(path, f'combined_plot_{plot_counter}.png')
            
        create_plot([os.path.join(path, f) for f in sel], out)
        plot_counter += 1
    
    print("\nAll graphs plotted successfully!")

# Run the program
main()
