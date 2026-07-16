import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Data
data = {
    'GPU': ['V100', 'A40', 'A100_40', 'A100_80', 'H100', 'B200'],
    'Utilization': [40.1, 62.4, 69.4, 62.2, 60.2, 34.2],
    'Bandwidth': [360.6, 434.1, 1079.5, 1203.2, 2019.7, 2631.8]
}

df = pd.DataFrame(data)

# Scale by 1/17 to get the Algorithmic (Effective) version
df['Alg_Utilization'] = df['Utilization'] / 17
df['Alg_Bandwidth'] = df['Bandwidth'] / 17

# Setting increased font sizes
TITLE_SIZE = 20
LABEL_SIZE = 16
TICK_SIZE = 14
ANNOTATION_SIZE = 12
LEGEND_SIZE = 14

fig, ax1 = plt.subplots(figsize=(14, 8))
x = np.arange(len(df['GPU']))
width = 0.35 

# Left Bar: Percentage of Peak Bandwidth
bars1 = ax1.bar(x - width/2, df['Alg_Utilization'], width, color='steelblue', alpha=0.8, label='Percentage of Peak Bandwidth (%)')
ax1.set_ylabel('Percentage of Peak Bandwidth (%)', fontweight='bold', color='steelblue', fontsize=LABEL_SIZE)
ax1.set_ylim(0, max(df['Alg_Utilization']) * 1.3)
ax1.tick_params(axis='y', labelcolor='steelblue', labelsize=TICK_SIZE)

# Right Bar: Achieved GPU Memory Bandwidth
ax2 = ax1.twinx()
bars2 = ax2.bar(x + width/2, df['Alg_Bandwidth'], width, color='firebrick', alpha=0.8, label='Achieved GPU Memory Bandwidth (GB/s)')
ax2.set_ylabel('Achieved GPU Memory Bandwidth (GB/s)', color='firebrick', fontweight='bold', fontsize=LABEL_SIZE)
ax2.tick_params(axis='y', labelcolor='firebrick', labelsize=TICK_SIZE)
ax2.set_ylim(0, max(df['Alg_Bandwidth']) * 1.3)

# Formatting
ax1.set_xticks(x)
ax1.set_xticklabels(df['GPU'], fontweight='bold', fontsize=TICK_SIZE)
ax1.set_xlabel('GPU Model', fontweight='bold', fontsize=LABEL_SIZE)
ax1.grid(axis='y', linestyle='--', alpha=0.3)

# Annotations function with larger text
def autolabel(rects, ax, unit="", fontsize=10):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}{unit}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 5), textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold', fontsize=fontsize)

autolabel(bars1, ax1, "%", fontsize=ANNOTATION_SIZE)
autolabel(bars2, ax2, fontsize=ANNOTATION_SIZE)

# Legend
lines, labels = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines + lines2, labels + labels2, loc='upper left', fontsize=LEGEND_SIZE)

plt.title('GPU Memory & Bandwidth Utilization (16 GB Input Volume)', fontsize=TITLE_SIZE, fontweight='bold', pad=25)
fig.tight_layout()
plt.savefig('updated_gpu_utilization.png', dpi=300)
plt.show()