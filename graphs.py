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

def create_plot(files, out_file):
    """Create a plot from data files and save as PNG"""
    fig = go.Figure()
    
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
            x_np = np.array(x)
            y_np = np.array(y)
            
            # Calculate last 20% of points
            n_points = len(x)
            last_20_percent = round(n_points * 0.2)
            x_last = x_np[-last_20_percent:]
            y_last = y_np[-last_20_percent:]
            
            # Add original data plot
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(width=1.5),
                                   name=os.path.splitext(os.path.basename(f))[0], showlegend=True))
            
            # Calculate regression line for last 20%
            slope, intercept = np.polyfit(x_last, y_last, 1)
            
            # Add regression line across full x range
            regression_y = slope * x_np + intercept
            fig.add_trace(go.Scatter(x=x, y=regression_y, mode='lines', 
                                   line=dict(width=3, dash='solid'),
                                   showlegend=True))
    
    # Customize and save plot if we have data
    if fig.data:
        # Get axis labels from user
        x_label = "Time [ns]"
        y_label = "Number of water molecules"
        
        fig.update_layout(
            template='seaborn',  # Use seaborn style
            margin=dict(l=20, r=20, t=20, b=20),  # Small margins
            
            # Legend settings
            legend=dict(
                y=-0.1,  # Position below the plot
                x=0.5,   # Center horizontally
                font=dict(size=20),  # Large text
                xanchor='center',  # Center the legend
                yanchor='top',     # Anchor to top of legend
                bgcolor='rgba(0,0,0,0)',  # Transparent background
                bordercolor='rgba(0,0,0,0)'  # Transparent border
            ),
            
            # Axis settings
            xaxis=dict(
                title=x_label,  # Custom X-axis label
                tickfont=dict(size=20),
                title_font=dict(size=20)
            ),
            yaxis=dict(
                title=y_label,  # Custom Y-axis label
                tickfont=dict(size=20),
                title_font=dict(size=20)
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
