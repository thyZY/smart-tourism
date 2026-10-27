import baseConfig from './playwright.config.mjs'

export default {
  ...baseConfig,
  grep: /@live-map/,
  grepInvert: undefined,
  projects: baseConfig.projects.filter(project => project.name === 'desktop'),
}
