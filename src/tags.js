export function extractTopTags(videos, topN=10) {
    const freq = {};
    for (const v of videos) {
      const words = (v.tags || v.title.split(/\s+/))
        .map(w => w.replace(/[^\w#]/g,'').toLowerCase())
        .filter(w => w.length>2);
      for (const w of words) freq[w] = (freq[w]||0)+1;
    }
    return Object.entries(freq)
      .sort((a,b)=>b[1]-a[1])
      .slice(0, topN)
      .map(([tag,count])=>({tag,count}));
  }
  