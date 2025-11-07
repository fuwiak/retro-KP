/**
 * Test script to verify YouTube subtitles fetching for a specific video
 * Video: https://www.youtube.com/watch?v=n8fUyiMAPJw
 * Video ID: n8fUyiMAPJw
 * 
 * NOTE: This test runs in Node.js, but YouTube subtitles may work better
 * in a browser environment due to CORS and YouTube's restrictions.
 * If this test fails, try testing in the browser console or in the actual app.
 */

const videoId = 'n8fUyiMAPJw';
const testUrl = 'https://www.youtube.com/watch?v=n8fUyiMAPJw&list=RDn8fUyiMAPJw&start_radio=1';

async function fetchYouTubeSubtitles(videoId) {
  console.log(`\n🔍 Testing subtitles fetch for video: ${videoId}`);
  console.log(`📺 URL: ${testUrl}\n`);

  const languages = ['en', 'pl', 'ru'];
  
  // Helper to parse response safely
  const tryParseJSON = async (res) => {
    try {
      const text = await res.text();
      if (!text || text.trim().length === 0) {
        return null;
      }
      // Try to parse as JSON
      try {
        return JSON.parse(text);
      } catch (e) {
        // If not JSON, might be XML or empty
        console.log(`    ⚠️ Response is not valid JSON (first 100 chars): ${text.substring(0, 100)}...`);
        return null;
      }
    } catch (e) {
      return null;
    }
  };
  
  // First try with specific languages
  for (const lang of languages) {
    try {
      const url = `https://www.youtube.com/api/timedtext?lang=${lang}&v=${videoId}&fmt=json3`;
      console.log(`  Trying ${lang}...`);
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });
      
      if (res.ok && res.status === 200) {
        const data = await tryParseJSON(res);
        if (data && data.events && Array.isArray(data.events) && data.events.length > 0) {
          const subtitles = parseSubtitles(data.events);
          if (subtitles.length > 0) {
            console.log(`  ✅ SUCCESS: Found ${subtitles.length} subtitle segments in ${lang}`);
            console.log(`  First few subtitles:`, subtitles.slice(0, 3));
            return subtitles;
          }
        }
      } else {
        console.log(`  ❌ HTTP ${res.status} for ${lang}`);
      }
    } catch (e) {
      console.log(`  ⚠️ Error for ${lang}: ${e.message}`);
      continue;
    }
  }
  
  // Try auto-generated captions (asr = automatic speech recognition)
  try {
    console.log(`  Trying auto-generated (asr)...`);
    const url = `https://www.youtube.com/api/timedtext?lang=en&v=${videoId}&fmt=json3&kind=asr`;
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (res.ok && res.status === 200) {
      const data = await tryParseJSON(res);
      if (data && data.events && Array.isArray(data.events) && data.events.length > 0) {
        const subtitles = parseSubtitles(data.events);
        if (subtitles.length > 0) {
          console.log(`  ✅ SUCCESS: Found ${subtitles.length} auto-generated subtitle segments`);
          console.log(`  First few subtitles:`, subtitles.slice(0, 3));
          return subtitles;
        }
      }
    } else {
      console.log(`  ❌ HTTP ${res.status} for auto-generated`);
    }
  } catch (e) {
    console.log(`  ⚠️ Auto-generated captions failed: ${e.message}`);
  }
  
  // Try with track parameter for auto-generated
  try {
    console.log(`  Trying track=asr method...`);
    const url = `https://www.youtube.com/api/timedtext?v=${videoId}&fmt=json3&tlang=en&track=asr`;
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (res.ok && res.status === 200) {
      const data = await tryParseJSON(res);
      if (data && data.events && Array.isArray(data.events) && data.events.length > 0) {
        const subtitles = parseSubtitles(data.events);
        if (subtitles.length > 0) {
          console.log(`  ✅ SUCCESS: Found ${subtitles.length} auto-generated subtitle segments (track method)`);
          console.log(`  First few subtitles:`, subtitles.slice(0, 3));
          return subtitles;
        }
      }
    } else {
      console.log(`  ❌ HTTP ${res.status} for track method`);
    }
  } catch (e) {
    console.log(`  ⚠️ Track method failed: ${e.message}`);
  }
  
  // Try without language specification (auto-detect)
  try {
    console.log(`  Trying auto-detect (no lang)...`);
    const url = `https://www.youtube.com/api/timedtext?v=${videoId}&fmt=json3`;
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    
    if (res.ok && res.status === 200) {
      const data = await tryParseJSON(res);
      if (data && data.events && Array.isArray(data.events) && data.events.length > 0) {
        const subtitles = parseSubtitles(data.events);
        if (subtitles.length > 0) {
          console.log(`  ✅ SUCCESS: Found ${subtitles.length} subtitle segments (auto-detect)`);
          console.log(`  First few subtitles:`, subtitles.slice(0, 3));
          return subtitles;
        }
      }
    } else {
      console.log(`  ❌ HTTP ${res.status} for auto-detect`);
    }
  } catch (e) {
    console.log(`  ⚠️ Auto-detect failed: ${e.message}`);
  }
  
  // Try XML format as fallback
  try {
    console.log(`  Trying XML format as fallback...`);
    const url = `https://www.youtube.com/api/timedtext?v=${videoId}&lang=en`;
    const res = await fetch(url);
    
    if (res.ok && res.status === 200) {
      const xmlText = await res.text();
      if (xmlText && xmlText.includes('<text')) {
        // Simple XML parsing using regex (for Node.js, we can't use DOMParser)
        const textMatches = xmlText.matchAll(/<text start="([^"]+)" dur="([^"]+)"[^>]*>([^<]+)<\/text>/g);
        const subtitles = [];
        
        for (const match of textMatches) {
          const start = parseFloat(match[1] || '0');
          const duration = parseFloat(match[2] || '0');
          const subtitleText = match[3] || '';
          
          if (subtitleText.trim()) {
            subtitles.push({
              text: subtitleText.trim(),
              start: start,
              duration: duration,
            });
          }
        }
        
        if (subtitles.length > 0) {
          console.log(`  ✅ SUCCESS: Found ${subtitles.length} subtitle segments (XML format)`);
          console.log(`  First few subtitles:`, subtitles.slice(0, 3));
          return subtitles;
        }
      }
    }
  } catch (e) {
    console.log(`  ⚠️ XML format failed: ${e.message}`);
  }
  
  throw new Error('No subtitles found. The video may not have captions or auto-generated captions enabled.');
}

function parseSubtitles(events) {
  const subtitles = [];
  for (const event of events) {
    if (event.segs && Array.isArray(event.segs)) {
      const text = event.segs
        .map(seg => seg.utf8 || '')
        .join('')
        .trim();
      
      if (text && text.length > 0) {
        subtitles.push({
          text: text,
          start: (event.tStartMs || 0) / 1000,
          duration: (event.dDurationMs || 0) / 1000,
        });
      }
    }
  }
  return subtitles;
}

// Test URL parsing
function getYouTubeVideoId(url) {
  const match =
    url.match(/v=([a-zA-Z0-9_-]{11})/) ||
    url.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/) ||
    url.match(/shorts\/([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : null;
}

// Run test
(async () => {
  try {
    console.log('🧪 YouTube Subtitles Test');
    console.log('='.repeat(50));
    
    // Test video ID extraction
    const extractedId = getYouTubeVideoId(testUrl);
    console.log(`\n📋 Video ID extraction:`);
    console.log(`  URL: ${testUrl}`);
    console.log(`  Extracted ID: ${extractedId}`);
    console.log(`  Expected ID: ${videoId}`);
    console.log(`  Match: ${extractedId === videoId ? '✅' : '❌'}`);
    
    if (extractedId !== videoId) {
      console.error('\n❌ TEST FAILED: Video ID extraction is incorrect!');
      process.exit(1);
    }
    
    // Test subtitles fetching
    const subtitles = await fetchYouTubeSubtitles(videoId);
    
    console.log('\n' + '='.repeat(50));
    console.log('✅ TEST PASSED');
    console.log(`📊 Total subtitles found: ${subtitles.length}`);
    console.log(`📝 Total text length: ${subtitles.reduce((sum, s) => sum + s.text.length, 0)} characters`);
    console.log(`⏱️  Duration range: ${subtitles[0].start.toFixed(2)}s - ${(subtitles[subtitles.length - 1].start + subtitles[subtitles.length - 1].duration).toFixed(2)}s`);
    
  } catch (error) {
    console.error('\n' + '='.repeat(50));
    console.error('❌ TEST FAILED');
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
})();

