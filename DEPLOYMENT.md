# Deployment Guide - Streamlit Cloud

## Overview
This guide will help you deploy the AI Pacing Agent to Streamlit Cloud for free.

## Prerequisites
- GitHub account
- Streamlit Cloud account (sign up at https://share.streamlit.io/)
- Your code is already on GitHub: https://github.com/alexandreganz/ai-pacing-agent

## Step-by-Step Deployment

### 1. Push Latest Changes to GitHub

First, commit and push the deployment configuration files:

```bash
cd lego-genai
git add .gitignore .streamlit/
git commit -m "Add Streamlit Cloud deployment configuration"
git push origin main
```

### 2. Sign Up for Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click "Sign up" and use your GitHub account
3. Authorize Streamlit to access your repositories

### 3. Deploy Your App

1. Click "New app" in Streamlit Cloud dashboard
2. Select your repository: `alexandreganz/ai-pacing-agent`
3. Set the branch: `main`
4. Set the main file path: `app.py`
5. Click "Deploy"

### 4. Configure Environment Variables (Optional)

The app works without environment variables (uses defaults), but you can configure:

1. In Streamlit Cloud, go to your app settings
2. Click "Advanced settings" → "Secrets"
3. Add the following (optional):

```toml
# Optional: Slack webhook for alerts
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Optional: Confidence threshold (default is 0.7)
CONFIDENCE_THRESHOLD = "0.7"
```

### 5. Access Your App

Once deployed, your app will be available at:
```
https://share.streamlit.io/alexandreganz/ai-pacing-agent/main/app.py
```

Or a custom subdomain like:
```
https://ai-pacing-agent-[random-id].streamlit.app
```

## App Features Available in Deployment

Your deployed app includes:
- **Interactive Dashboard**: Real-time pacing analysis visualization
- **Scenario Testing**: Test different variance scenarios
- **Multi-Platform Support**: Google, Meta, DV360 campaigns
- **Decision Flow Visualization**: See how the AI agent makes decisions
- **Results Tracking**: Compare different agent runs
- **Audit Logs**: Full decision audit trail

## Important Notes

### Current Deployment Status
- **Phase**: MVP with Mock APIs
- **Data**: Simulated campaign data (no real API connections)
- **Perfect for**: Demos, interviews, presentations

### Performance
- Free tier limitations:
  - App sleeps after 7 days of inactivity
  - Limited to 1 GB RAM
  - Shared CPU resources
- Expected load time: 10-30 seconds on first visit
- Subsequent loads: 2-5 seconds

### Future Enhancements (Phase 2+)

When you're ready to connect real APIs:

1. Add API credentials to Streamlit Secrets:
```toml
[google_ads]
client_id = "your-client-id"
client_secret = "your-client-secret"
refresh_token = "your-refresh-token"

[meta_ads]
access_token = "your-access-token"
```

2. Update code to use real API clients instead of mocks
3. Consider upgrading to Streamlit Cloud Teams for better performance

## Troubleshooting

### App Won't Start
- Check logs in Streamlit Cloud dashboard
- Verify all dependencies are in requirements.txt
- Ensure Python version compatibility (3.12)

### Module Import Errors
- Make sure all source files are committed to GitHub
- Check that src/ directory structure is preserved

### Performance Issues
- Mock API should be fast (2-3 seconds per campaign)
- If slow, check Streamlit Cloud resource usage
- Consider caching with @st.cache_data

## Monitoring

### View Logs
1. Go to Streamlit Cloud dashboard
2. Click on your app
3. Click "Manage app" → "Logs"

### Check Usage
- Monitor in Streamlit Cloud dashboard
- View metrics: visitors, uptime, resource usage

## Updating Your Deployment

To update the live app:

```bash
git add .
git commit -m "Update feature X"
git push origin main
```

Streamlit Cloud will automatically redeploy within 1-2 minutes.

## Cost

**Free Tier Includes**:
- Unlimited public apps
- Community support
- Basic resources (1 GB RAM, shared CPU)

**No credit card required for basic deployment!**

## Support Resources

- Streamlit Docs: https://docs.streamlit.io/
- Streamlit Cloud Docs: https://docs.streamlit.io/streamlit-community-cloud
- Community Forum: https://discuss.streamlit.io/

## Next Steps After Deployment

1. Share your app URL with stakeholders
2. Gather feedback on the demo
3. Plan Phase 2: Real API integration
4. Consider custom domain (requires Teams plan)

---

**Deployed App Status**: MVP Phase 1 - Mock APIs
**Ready for**: Demos, Interviews, Presentations
**Next Phase**: Real API Integration (Phase 2)
