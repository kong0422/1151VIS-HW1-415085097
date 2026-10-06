<script setup>
import '@/assets/bootstrap-5.3.2/css/bootstrap-reboot.min.css'
import '@/assets/bootstrap-5.3.2/css/bootstrap.min.css'
import '@/assets/bootstrap-5.3.2/js/bootstrap.bundle.min.js'
import '@/assets/main.css'
</script>

<template>
  <main>
    <RouterView
      :env="env" :page_title="page_title"
      :client_info="client_info"
      :API_KEY="API_KEY"
      :API_URL="API_URL"
    />
  </main>
</template>

<script>
export default {
  data() {
    return {
      env: import.meta.env.MODE,
      page_title: import.meta.env.VITE_TITLE,

      // 中央氣象署 API 設定

      API_KEY: 'CWA-22E9C318-4D92-4C32-B734-9BE27E3B1005',
      DATA_ID: 'O-A0001-001', // 氣象觀測站-全測站逐時氣象資料
      API_URL: '',
      client_info: {}
    }
  },

  provide() {
    return {
      getMyData: this.getMyData,
      setMyData: this.setMyData
    }
  },

  created () {
    // this.client_info = this.getClientInfo()
    this.API_URL = `https://cwa.gov.tw${this.DATA_ID}?Authorization=${this.API_KEY}`;
  },

  mounted() {
  },

  methods: {
    getMyData (item) {
      let data = localStorage.getItem(item) || null
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data)
        } catch (e) {
        }
      }
      return data
    },
    setMyData (item, data) {
      if (typeof data === 'object') {
        data = JSON.stringify(data)
      }
      localStorage.setItem(item, data)
    },
    getClientInfo () {
      var info = {
        device: null,
        browser: null,
        os: null,
        language: (navigator.browserLanguage || navigator.language).toLowerCase()
      }
      // eslint-disable-next-line
      var ua, isWindowsPhone, isSymbian, isAndroid, isFireFox, isChrome, isSafari, isTablet, isPhone, isPc
      ua = navigator.userAgent
      if (/(?:Windows Phone)/.test(ua)) {
        isWindowsPhone = true
        info.browser = 'Windows Phone'
      }
      if (/(?:SymbianOS)/.test(ua) || isWindowsPhone) {
        isSymbian = true
      }
      if (/(?:Android)/.test(ua)) {
        isAndroid = true
        info.device = 'Mobile'
        info.os = 'Android'
      }
      if (/(?:Firefox)/.test(ua)) {
        isFireFox = true
        info.browser = 'Firefox'
      }
      if (/(?:Chrome|CriOS)/.test(ua)) {
        isChrome = true
        info.browser = 'Chrome'
      }
      if (/safari/i.test(ua) && (!/chrome/i.test(ua))) {
        isSafari = true
        info.browser = 'Safari'
        info.os = 'Mac'
      }
      if (/(?:iPad|PlayBook)/.test(ua) || (isAndroid && !/(?:Mobile)/.test(ua)) || (isFireFox && /(?:Tablet)/.test(ua))) {
        isTablet = true
        info.device = 'Tablet'
      }
      if (/(?:iPhone)/.test(ua) && !isTablet) {
        isPhone = true
        info.device = 'Mobile'
      }
      if (!isPhone && !isAndroid && !isSymbian) {
        isPc = true
        info.device = 'PC'
      }
      if (info.device === 'PC' && !info.os) {
        info.os = 'Windows'
      }
      console.log(info)
      return info
    }
  }

}
</script>
