export async function fetchYouTubeTrending(apiKey, region = 'US', maxResults = 10) {
  try {
    const url = `https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&chart=mostPopular&maxResults=${maxResults}&regionCode=${region}&key=${apiKey}`;
    const r = await fetch(url);
    
    if (!r.ok) {
      throw new Error(`YouTube API error: ${r.status} ${r.statusText}`);
    }
    
    const js = await r.json();
    
    if (!js.items || js.items.length === 0) {
      return [];
    }
    
    return js.items.map(v => {
      const views = parseInt(v.statistics.viewCount || 0);
      const likes = parseInt(v.statistics.likeCount || 0);
      const dislikes = parseInt(v.statistics.dislikeCount || 0);
      const comments = parseInt(v.statistics.commentCount || 0);
      const totalReactions = likes + dislikes;
      const likeRatio = totalReactions > 0 ? (likes / totalReactions * 100).toFixed(1) : 0;
      
      // Calculate hours since upload (approximate)
      const publishedAt = new Date(v.snippet.publishedAt);
      const hoursSinceUpload = Math.max(1, (Date.now() - publishedAt.getTime()) / (1000 * 60 * 60));
      const relativeGrowth = views / hoursSinceUpload;
      
      return {
        id: v.id,
        title: v.snippet.title,
        description: v.snippet.description || '',
        channelTitle: v.snippet.channelTitle || 'Unknown',
        channelId: v.snippet.channelId || '',
        tags: v.snippet.tags || [],
        thumbnail: v.snippet.thumbnails?.medium?.url || v.snippet.thumbnails?.default?.url || '',
        thumbnailHigh: v.snippet.thumbnails?.high?.url || v.snippet.thumbnails?.medium?.url || '',
        publishedAt: v.snippet.publishedAt,
        categoryId: v.snippet.categoryId || '',
        views: views,
        likes: likes,
        dislikes: dislikes,
        comments: comments,
        likeRatio: parseFloat(likeRatio),
        duration: v.contentDetails?.duration || '',
        relativeGrowth: Math.round(relativeGrowth),
        hoursSinceUpload: Math.round(hoursSinceUpload),
        url: `https://www.youtube.com/watch?v=${v.id}`
      };
    });
  } catch (error) {
    console.error('Error fetching YouTube trending:', error);
    throw error;
  }
}
  
  export async function fetchVKTrending(token) {
    const url = `https://api.vk.com/method/video.getPopular?count=50&access_token=${token}&v=5.131`;
    const r = await fetch(url);
    const js = await r.json();
    return js.response.items.map(v => ({
      id: v.id,
      title: v.title,
      views: v.views,
      likes: v.likes?.count || 0
    }));
  }
  