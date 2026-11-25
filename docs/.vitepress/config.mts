import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'bath-toy-boat-mk2',
  description: 'HRX-02 AQUA-VANGUARD — Watertight Zero-Support Print-in-Place Rescue Cruiser',
  base: '/bath-toy-boat-mk2/',
  cleanUrls: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/bath-toy-boat-mk2/icon.svg' }],
  ],
  themeConfig: {
    logo: '/icon.svg',
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Sunwood-ai-labs/bath-toy-boat-mk2' },
    ],
    search: { provider: 'local' },
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 Sunwood AI Labs',
    },
  },
  locales: {
    root: {
      label: 'English',
      lang: 'en-US',
      themeConfig: {
        nav: [
          { text: 'Naval & CAE', link: '/guide/engineering' },
          { text: '3D Printing', link: '/guide/printing' },
        ],
        sidebar: [
          {
            text: 'Guide',
            items: [
              { text: 'Naval & CAE Verification', link: '/guide/engineering' },
              { text: 'AMS 3-Color Printing', link: '/guide/printing' },
            ],
          },
        ],
      },
    },
    ja: {
      label: '日本語',
      lang: 'ja-JP',
      link: '/ja/',
      title: 'bath-toy-boat-mk2',
      description: 'おふろレスキュー艇 Mk-II 設計・流体・構造解析ドキュメント',
      themeConfig: {
        nav: [
          { text: '造船工学・CAE', link: '/ja/guide/engineering' },
          { text: '3Dプリントガイド', link: '/ja/guide/printing' },
        ],
        sidebar: [
          {
            text: 'ガイド',
            items: [
              { text: '造船工学・CAE 検証', link: '/ja/guide/engineering' },
              { text: 'AMS 3色プリント手順', link: '/ja/guide/printing' },
            ],
          },
        ],
      },
    },
  },
})
