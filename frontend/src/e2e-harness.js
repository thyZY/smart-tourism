import { createApp } from 'vue'
import AIItineraryPanel from './components/AIItineraryPanel.vue'
import './style.css'
const root = document.getElementById('app')
root.style.cssText = 'max-width:480px;margin:0 auto;padding:12px;min-height:100vh;box-sizing:border-box'
document.body.style.cssText = 'margin:0;background:#f3f7fc'
createApp(AIItineraryPanel).mount(root)
