# benchmark.py
import requests
import matplotlib.pyplot as plt
import numpy as np

videos = [
    ("https://www.youtube.com/watch?v=rl7B-LHiaNo", "6min (Dwarkesh)"),
    ("https://www.youtube.com/watch?v=nr8biZfSZ3Y", "13min (Carter)"),
    ("https://www.youtube.com/watch?v=riniamTdUSo", "22min (Lex)"),
    ("https://www.youtube.com/watch?v=zaXKQ70q4KQ", "33min (Veritasium)"),
    ("https://www.youtube.com/watch?v=WXuK6gekU1Y", "90min (DeepMind)"),
    ("https://www.youtube.com/watch?v=xH76q6yYVlk", "103min (All-In)"),
    ("https://www.youtube.com/watch?v=_TFL2dGViuw", "130min (Need4Speed)")
]

results = []
for url, label in videos:
    print(f"\nProcessing {label}...")
    response = requests.post('http://localhost:8080/transcribe_benchmark', data={'url': url})
    data = response.json()
    results.append({
        'label': label,
        'length': data['video_length'] / 60,  # convert to minutes
        'time': data['elapsed_time'] / 60  # convert to minutes
    })
    print(f"Done: {data['elapsed_time']/60:.1f} minutes")

# Plot results
plt.figure(figsize=(12, 8))
lengths = [r['length'] for r in results]
times = [r['time'] for r in results]
plt.scatter(lengths, times)

# Calculate and plot trend line
z = np.polyfit(lengths, times, 1)
p = np.poly1d(z)
plt.plot(lengths, p(lengths), '--', alpha=0.5, color='gray', 
         label=f'Trend: {z[0]:.2f}x + {z[1]:.2f}')

for r in results:
    plt.annotate(f"{r['label']}\n{r['time']:.1f}m",
                (r['length'], r['time']),
                xytext=(0, 10), textcoords='offset points',
                ha='center')

plt.xlabel('Video Length (minutes)')
plt.ylabel('Processing Time (minutes)')
plt.title('Transcription Processing Time vs Video Length')
plt.grid(True, alpha=0.3)
plt.legend()

# Add processing rate on the plot
avg_rate = np.mean([r['length']/r['time'] for r in results])
plt.text(0.02, 0.98, f'Average processing rate: {avg_rate:.1f}x realtime', 
         transform=plt.gca().transAxes, verticalalignment='top')

plt.tight_layout()
plt.savefig('processing_times.png', dpi=300)
print("\nPlot saved as processing_times.png")

# Print detailed stats
print("\nDetailed Statistics:")
for r in results:
    rate = r['length']/r['time']
    print(f"{r['label']}:")
    print(f"  Length: {r['length']:.1f}m")
    print(f"  Processing time: {r['time']:.1f}m")
    print(f"  Processing rate: {rate:.1f}x realtime")