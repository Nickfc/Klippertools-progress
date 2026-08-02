# Cumulative v0.8 finalizer failure

Run: 30750271409
Commit: 2967f6b97a4e467ac0d250c1de6b38813c4f8b1a

```text
/home/runner/work/_temp/v08-source-overlay.tar.xz: OK
patching file src/components/mixins/dashboard.ts
patching file src/locales/da.json
patching file src/locales/en.json
patching file src/pages/Dashboard.vue
patching file src/store/gui/getters.ts
patching file src/store/gui/index.ts
patching file src/store/variables.ts
patching file src/components/mixins/dashboard.ts
patching file src/locales/da.json
patching file src/locales/en.json
patching file src/pages/Dashboard.vue
patching file src/store/gui/getters.ts
patching file src/store/gui/index.ts
patching file src/store/variables.ts
npm warn deprecated sourcemap-codec@1.4.8: Please use @jridgewell/sourcemap-codec instead
npm warn deprecated source-map@0.8.0-beta.0: The work that was done in this beta branch won't be included in future versions
npm warn deprecated vue@2.7.16: Vue 2 has reached EOL and is no longer actively maintained. See https://v2.vuejs.org/eol/ for more details.

added 847 packages in 24s

/home/runner/work/_temp/mainsail-build-work/v2.17.0/src/components/mixins/dashboard.ts
  19:5  warning  'mdiHistory' is defined but never used  @typescript-eslint/no-unused-vars

✖ 1 problem (0 errors, 1 warning)


> mainsail@2.17.0 build
> vite build && npm run build.zip

[36mvite v5.4.21 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 3951 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mmanifest.webmanifest                             [39m[1m[2m    0.50 kB[22m[1m[22m
[2mdist/[22m[32mindex.html                                       [39m[1m[2m    2.15 kB[22m[1m[22m[2m │ gzip:   0.79 kB[22m
[2mdist/[22m[2massets/[22m[35mJanusStreamer-BRNQ5Tpp.css                [39m[1m[2m    0.06 kB[22m[1m[22m[2m │ gzip:   0.08 kB[22m
[2mdist/[22m[2massets/[22m[35mJMuxerStream-Ghy5S_h3.css                 [39m[1m[2m    0.06 kB[22m[1m[22m[2m │ gzip:   0.08 kB[22m
[2mdist/[22m[2massets/[22m[35mWebrtcCameraStreamer-BRNlGQUz.css         [39m[1m[2m    0.06 kB[22m[1m[22m[2m │ gzip:   0.08 kB[22m
[2mdist/[22m[2massets/[22m[35mWebrtcMediaMTX-B5-Yoyes.css               [39m[1m[2m    0.06 kB[22m[1m[22m[2m │ gzip:   0.08 kB[22m
[2mdist/[22m[2massets/[22m[35mWebrtcGo2rtc-Bsaeny4h.css                 [39m[1m[2m    0.06 kB[22m[1m[22m[2m │ gzip:   0.08 kB[22m
[2mdist/[22m[2massets/[22m[35mHeightmap-CpnWqGHX.css                    [39m[1m[2m    0.21 kB[22m[1m[22m[2m │ gzip:   0.13 kB[22m
[2mdist/[22m[2massets/[22m[35mMjpegstreamer-DqaKUdZ_.css                [39m[1m[2m    0.29 kB[22m[1m[22m[2m │ gzip:   0.21 kB[22m
[2mdist/[22m[2massets/[22m[35mMjpegstreamerAdaptive-XhKyIuw0.css        [39m[1m[2m    0.29 kB[22m[1m[22m[2m │ gzip:   0.21 kB[22m
[2mdist/[22m[2massets/[22m[35mWebcamNozzleCrosshair-ic6H6w5D.css        [39m[1m[2m    0.40 kB[22m[1m[22m[2m │ gzip:   0.22 kB[22m
[2mdist/[22m[2massets/[22m[35mViewer-DhDSIvud.css                       [39m[1m[2m    0.59 kB[22m[1m[22m[2m │ gzip:   0.30 kB[22m
[2mdist/[22m[2massets/[22m[35moverlayscrollbars-BJn_P54_.css            [39m[1m[2m   19.99 kB[22m[1m[22m[2m │ gzip:   4.58 kB[22m
[2mdist/[22m[2massets/[22m[35mindex-DOW_gi1J.css                        [39m[1m[2m   59.39 kB[22m[1m[22m[2m │ gzip:  13.46 kB[22m
[2mdist/[22m[2massets/[22m[35mvuetify-BSwS9o2d.css                      [39m[1m[2m  529.18 kB[22m[1m[22m[2m │ gzip:  65.10 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlurVaryingDeclaration-C0qnyMq_.js  [39m[1m[2m    0.14 kB[22m[1m[22m[2m │ gzip:   0.15 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlurVaryingDeclaration-DEp5Z2ny.js  [39m[1m[2m    0.15 kB[22m[1m[22m[2m │ gzip:   0.16 kB[22m
[2mdist/[22m[2massets/[22m[36mlogDepthDeclaration-D_H16P16.js           [39m[1m[2m    0.21 kB[22m[1m[22m[2m │ gzip:   0.20 kB[22m
[2mdist/[22m[2massets/[22m[36mlogDepthFragment-DTlpatAl.js              [39m[1m[2m    0.24 kB[22m[1m[22m[2m │ gzip:   0.22 kB[22m
[2mdist/[22m[2massets/[22m[36mlogDepthVertex-Cj1b4f10.js                [39m[1m[2m    0.31 kB[22m[1m[22m[2m │ gzip:   0.24 kB[22m
[2mdist/[22m[2massets/[22m[36mvertexColorMixing-CvDooCuG.js             [39m[1m[2m    0.36 kB[22m[1m[22m[2m │ gzip:   0.24 kB[22m
[2mdist/[22m[2massets/[22m[36mpass.fragment-BBGK6O1l.js                 [39m[1m[2m    0.46 kB[22m[1m[22m[2m │ gzip:   0.33 kB[22m
[2mdist/[22m[2massets/[22m[36mmeshUboDeclaration-CiQH4Nrv.js            [39m[1m[2m    0.52 kB[22m[1m[22m[2m │ gzip:   0.31 kB[22m
[2mdist/[22m[2massets/[22m[36mrgbdDecode.fragment-PLXOyizj.js           [39m[1m[2m    0.56 kB[22m[1m[22m[2m │ gzip:   0.39 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapMerge.vertex-De0bZc6q.js           [39m[1m[2m    0.58 kB[22m[1m[22m[2m │ gzip:   0.38 kB[22m
[2mdist/[22m[2massets/[22m[36mpass.fragment-BN3--opx.js                 [39m[1m[2m    0.59 kB[22m[1m[22m[2m │ gzip:   0.38 kB[22m
[2mdist/[22m[2massets/[22m[36mrgbdDecode.fragment-D8T067Yj.js           [39m[1m[2m    0.65 kB[22m[1m[22m[2m │ gzip:   0.42 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapMerge.vertex-S7TrybPr.js           [39m[1m[2m    0.68 kB[22m[1m[22m[2m │ gzip:   0.42 kB[22m
[2mdist/[22m[2massets/[22m[36mline.fragment-CL-ClIq2.js                 [39m[1m[2m    0.68 kB[22m[1m[22m[2m │ gzip:   0.43 kB[22m
[2mdist/[22m[2massets/[22m[36mpostprocess.vertex-QwV_wQfa.js            [39m[1m[2m    0.73 kB[22m[1m[22m[2m │ gzip:   0.45 kB[22m
[2mdist/[22m[2massets/[22m[36mvertexColorMixing-DZyQZAeV.js             [39m[1m[2m    0.76 kB[22m[1m[22m[2m │ gzip:   0.36 kB[22m
[2mdist/[22m[2massets/[22m[36mline.fragment-D4K-0R6U.js                 [39m[1m[2m    0.80 kB[22m[1m[22m[2m │ gzip:   0.44 kB[22m
[2mdist/[22m[2massets/[22m[36mvirtual_pwa-register-7QtbIe2t.js          [39m[1m[2m    0.86 kB[22m[1m[22m[2m │ gzip:   0.52 kB[22m
[2mdist/[22m[2massets/[22m[36mcolor.fragment-B7TjRvpL.js                [39m[1m[2m    0.87 kB[22m[1m[22m[2m │ gzip:   0.45 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlur.vertex-UxMCK5re.js             [39m[1m[2m    0.88 kB[22m[1m[22m[2m │ gzip:   0.50 kB[22m
[2mdist/[22m[2massets/[22m[36msk-B303QlGc.js                            [39m[1m[2m    0.91 kB[22m[1m[22m[2m │ gzip:   0.49 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapMerge.fragment-VtnO_VND.js         [39m[1m[2m    0.96 kB[22m[1m[22m[2m │ gzip:   0.51 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlur.vertex-GdTqCOpC.js             [39m[1m[2m    1.02 kB[22m[1m[22m[2m │ gzip:   0.54 kB[22m
[2mdist/[22m[2massets/[22m[36mcolor.fragment-BKhB8qFg.js                [39m[1m[2m    1.04 kB[22m[1m[22m[2m │ gzip:   0.51 kB[22m
[2mdist/[22m[2massets/[22m[36mfogFragment-b8R0vCU2.js                   [39m[1m[2m    1.10 kB[22m[1m[22m[2m │ gzip:   0.50 kB[22m
[2mdist/[22m[2massets/[22m[36mfxaa.vertex-DWxAxM9l.js                   [39m[1m[2m    1.15 kB[22m[1m[22m[2m │ gzip:   0.48 kB[22m
[2mdist/[22m[2massets/[22m[36mclipPlaneFragment-BGxauOiu.js             [39m[1m[2m    1.19 kB[22m[1m[22m[2m │ gzip:   0.33 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapMerge.fragment-C_pRkCEG.js         [39m[1m[2m    1.20 kB[22m[1m[22m[2m │ gzip:   0.58 kB[22m
[2mdist/[22m[2massets/[22m[36mmainUVVaryingDeclaration-B8zhK2k5.js      [39m[1m[2m    1.22 kB[22m[1m[22m[2m │ gzip:   0.54 kB[22m
[2mdist/[22m[2massets/[22m[36mclipPlaneVertex-Cm783hJI.js               [39m[1m[2m    1.26 kB[22m[1m[22m[2m │ gzip:   0.33 kB[22m
[2mdist/[22m[2massets/[22m[36mglowBlurPostProcess.fragment-DG4cUbiz.js  [39m[1m[2m    1.27 kB[22m[1m[22m[2m │ gzip:   0.66 kB[22m
[2mdist/[22m[2massets/[22m[36mcolor.vertex-DGlh44p4.js                  [39m[1m[2m    1.31 kB[22m[1m[22m[2m │ gzip:   0.61 kB[22m
[2mdist/[22m[2massets/[22m[36mcolor.vertex-CWyJMJsO.js                  [39m[1m[2m    1.38 kB[22m[1m[22m[2m │ gzip:   0.62 kB[22m
[2mdist/[22m[2massets/[22m[36mHtmlVideo-CDKYMtyR.js                     [39m[1m[2m    1.46 kB[22m[1m[22m[2m │ gzip:   0.79 kB[22m
[2mdist/[22m[2massets/[22m[36mddsTextureLoader-DHtVO0nw.js              [39m[1m[2m    1.47 kB[22m[1m[22m[2m │ gzip:   0.73 kB[22m
[2mdist/[22m[2massets/[22m[36mHtmlIframe-wdueZHHk.js                    [39m[1m[2m    1.50 kB[22m[1m[22m[2m │ gzip:   0.81 kB[22m
[2mdist/[22m[2massets/[22m[36mmainUVVaryingDeclaration-BEhf1iLL.js      [39m[1m[2m    1.52 kB[22m[1m[22m[2m │ gzip:   0.50 kB[22m
[2mdist/[22m[2massets/[22m[36mglowBlurPostProcess.fragment-B7uZ3loo.js  [39m[1m[2m    1.55 kB[22m[1m[22m[2m │ gzip:   0.74 kB[22m
[2mdist/[22m[2massets/[22m[36mfxaa.vertex-F6xOLwWl.js                   [39m[1m[2m    1.57 kB[22m[1m[22m[2m │ gzip:   0.53 kB[22m
[2mdist/[22m[2massets/[22m[36mWebcamNozzleCrosshair-DPA1oXCy.js         [39m[1m[2m    1.62 kB[22m[1m[22m[2m │ gzip:   0.81 kB[22m
[2mdist/[22m[2massets/[22m[36mline.vertex-DiwwpGpZ.js                   [39m[1m[2m    1.80 kB[22m[1m[22m[2m │ gzip:   0.77 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapGeneration.fragment-Dufs76Lu.js    [39m[1m[2m    1.92 kB[22m[1m[22m[2m │ gzip:   0.76 kB[22m
[2mdist/[22m[2massets/[22m[36mline.vertex-BByBEITe.js                   [39m[1m[2m    1.94 kB[22m[1m[22m[2m │ gzip:   0.79 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapGeneration.vertex-BhiqkVcA.js      [39m[1m[2m    2.31 kB[22m[1m[22m[2m │ gzip:   0.78 kB[22m
[2mdist/[22m[2massets/[22m[36mmorphTargetsVertex-BTVnpJFA.js            [39m[1m[2m    2.45 kB[22m[1m[22m[2m │ gzip:   0.70 kB[22m
[2mdist/[22m[2massets/[22m[36mcubemapToSphericalPolynomial-ByybCv08.js  [39m[1m[2m    2.52 kB[22m[1m[22m[2m │ gzip:   1.16 kB[22m
[2mdist/[22m[2massets/[22m[36mUv4lMjpeg-D1cEKtzw.js                     [39m[1m[2m    2.54 kB[22m[1m[22m[2m │ gzip:   1.12 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapGeneration.fragment-B9u2vcL6.js    [39m[1m[2m    2.54 kB[22m[1m[22m[2m │ gzip:   0.86 kB[22m
[2mdist/[22m[2massets/[22m[36mhdrTextureLoader-C7yzGa2C.js              [39m[1m[2m    2.59 kB[22m[1m[22m[2m │ gzip:   1.26 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlur.fragment-BChwTNr1.js           [39m[1m[2m    2.66 kB[22m[1m[22m[2m │ gzip:   0.93 kB[22m
[2mdist/[22m[2massets/[22m[36mglowMapGeneration.vertex-BxIwf4o2.js      [39m[1m[2m    2.73 kB[22m[1m[22m[2m │ gzip:   0.87 kB[22m
[2mdist/[22m[2massets/[22m[36mmorphTargetsVertex-uTSclvZE.js            [39m[1m[2m    3.07 kB[22m[1m[22m[2m │ gzip:   0.82 kB[22m
[2mdist/[22m[2massets/[22m[36mkernelBlur.fragment-C3UIVtdL.js           [39m[1m[2m    3.21 kB[22m[1m[22m[2m │ gzip:   1.01 kB[22m
[2mdist/[22m[2massets/[22m[36mbonesVertex-BJsVL_I_.js                   [39m[1m[2m    3.67 kB[22m[1m[22m[2m │ gzip:   0.75 kB[22m
[2mdist/[22m[2massets/[22m[36mtgaTextureLoader-CHX-mtG0.js              [39m[1m[2m    3.69 kB[22m[1m[22m[2m │ gzip:   1.47 kB[22m
[2mdist/[22m[2massets/[22m[36mhelperFunctions-BuxhDd1e.js               [39m[1m[2m    5.06 kB[22m[1m[22m[2m │ gzip:   1.62 kB[22m
[2mdist/[22m[2massets/[22m[36mMjpegstreamerAdaptive-BHk15LJJ.js         [39m[1m[2m    5.17 kB[22m[1m[22m[2m │ gzip:   1.93 kB[22m
[2mdist/[22m[2massets/[22m[36mWebrtcGo2rtc-ycK71tfR.js                  [39m[1m[2m    5.31 kB[22m[1m[22m[2m │ gzip:   2.20 kB[22m
[2mdist/[22m[2massets/[22m[36mworkbox-window.prod.es5-BiUm-Zq1.js       [39m[1m[2m    5.72 kB[22m[1m[22m[2m │ gzip:   2.35 kB[22m
[2mdist/[22m[2massets/[22m[36mfxaa.fragment-DTfPbW47.js                 [39m[1m[2m    5.75 kB[22m[1m[22m[2m │ gzip:   1.73 kB[22m
[2mdist/[22m[2massets/[22m[36mbakedVertexAnimation-4EsPuKdv.js          [39m[1m[2m    5.91 kB[22m[1m[22m[2m │ gzip:   1.16 kB[22m
[2mdist/[22m[2massets/[22m[36mWebrtcCameraStreamer-yZHlNmTi.js          [39m[1m[2m    6.04 kB[22m[1m[22m[2m │ gzip:   2.45 kB[22m
[2mdist/[22m[2massets/[22m[36mMjpegstreamer-CZYXtC7T.js                 [39m[1m[2m    6.25 kB[22m[1m[22m[2m │ gzip:   2.51 kB[22m
[2mdist/[22m[2massets/[22m[36mfxaa.fragment-ICUQsw2C.js                 [39m[1m[2m    6.62 kB[22m[1m[22m[2m │ gzip:   1.79 kB[22m
[2mdist/[22m[2massets/[22m[36menvTextureLoader-DvV3BeS8.js              [39m[1m[2m    7.07 kB[22m[1m[22m[2m │ gzip:   2.93 kB[22m
[2mdist/[22m[2massets/[22m[36mWebrtcMediaMTX-CKI2hlYR.js                [39m[1m[2m    7.22 kB[22m[1m[22m[2m │ gzip:   2.89 kB[22m
[2mdist/[22m[2massets/[22m[36mbasisTextureLoader-D73sPrtK.js            [39m[1m[2m    8.36 kB[22m[1m[22m[2m │ gzip:   3.32 kB[22m
[2mdist/[22m[2massets/[22m[36mdds-BRUIW4jb.js                           [39m[1m[2m    9.37 kB[22m[1m[22m[2m │ gzip:   3.53 kB[22m
[2mdist/[22m[2massets/[22m[36mCodemirror-CGGt7agv.js                    [39m[1m[2m   12.97 kB[22m[1m[22m[2m │ gzip:   4.46 kB[22m
[2mdist/[22m[2massets/[22m[36mdefault.vertex-BBW3X3T0.js                [39m[1m[2m   13.59 kB[22m[1m[22m[2m │ gzip:   3.11 kB[22m
[2mdist/[22m[2massets/[22m[36mexrTextureLoader-SXZi-7VF.js              [39m[1m[2m   14.95 kB[22m[1m[22m[2m │ gzip:   5.70 kB[22m
[2mdist/[22m[2massets/[22m[36mdefault.vertex-CcbjUvcE.js                [39m[1m[2m   15.11 kB[22m[1m[22m[2m │ gzip:   3.15 kB[22m
[2mdist/[22m[2massets/[22m[36mktxTextureLoader-gS5OO7iY.js              [39m[1m[2m   15.70 kB[22m[1m[22m[2m │ gzip:   4.67 kB[22m
[2mdist/[22m[2massets/[22m[36mzh_TW-BiL12nRY.js                         [39m[1m[2m   24.90 kB[22m[1m[22m[2m │ gzip:  13.88 kB[22m
[2mdist/[22m[2massets/[22m[36mja-DAsdMgq-.js                            [39m[1m[2m   26.85 kB[22m[1m[22m[2m │ gzip:  13.49 kB[22m
[2mdist/[22m[2massets/[22m[36mko-DvMVVTO3.js                            [39m[1m[2m   27.64 kB[22m[1m[22m[2m │ gzip:  13.91 kB[22m
[2mdist/[22m[2massets/[22m[36mzh-B7S78EIg.js                            [39m[1m[2m   37.28 kB[22m[1m[22m[2m │ gzip:  20.19 kB[22m
[2mdist/[22m[2massets/[22m[36mnl-C3ju2IW6.js                            [39m[1m[2m   38.95 kB[22m[1m[22m[2m │ gzip:  13.16 kB[22m
[2mdist/[22m[2massets/[22m[36mpt-xi-NpSA_.js                            [39m[1m[2m   39.58 kB[22m[1m[22m[2m │ gzip:  13.33 kB[22m
[2mdist/[22m[2massets/[22m[36mtr-zOmnN4My.js                            [39m[1m[2m   41.06 kB[22m[1m[22m[2m │ gzip:  14.58 kB[22m
[2mdist/[22m[2massets/[22m[36mpl-CWhqMIU7.js                            [39m[1m[2m   43.41 kB[22m[1m[22m[2m │ gzip:  15.43 kB[22m
[2mdist/[22m[2massets/[22m[36mse-Cn9Sb-Ng.js                            [39m[1m[2m   43.68 kB[22m[1m[22m[2m │ gzip:  15.05 kB[22m
[2mdist/[22m[2massets/[22m[36muk-Pa8Qqtyo.js                            [39m[1m[2m   47.24 kB[22m[1m[22m[2m │ gzip:  19.43 kB[22m
[2mdist/[22m[2massets/[22m[36mfr-CBN_6kdk.js                            [39m[1m[2m   47.96 kB[22m[1m[22m[2m │ gzip:  15.73 kB[22m
[2mdist/[22m[2massets/[22m[36mda-CDQuwckg.js                            [39m[1m[2m   48.81 kB[22m[1m[22m[2m │ gzip:  16.84 kB[22m
[2mdist/[22m[2massets/[22m[36mit-ClwfbRf6.js                            [39m[1m[2m   50.16 kB[22m[1m[22m[2m │ gzip:  16.40 kB[22m
[2mdist/[22m[2massets/[22m[36mcz-CvFrdRAO.js                            [39m[1m[2m   50.29 kB[22m[1m[22m[2m │ gzip:  18.07 kB[22m
[2mdist/[22m[2massets/[22m[36mhu-Brwg4WkO.js                            [39m[1m[2m   50.33 kB[22m[1m[22m[2m │ gzip:  18.33 kB[22m
[2mdist/[22m[2massets/[22m[36mes-BsGSvpaW.js                            [39m[1m[2m   51.26 kB[22m[1m[22m[2m │ gzip:  16.97 kB[22m
[2mdist/[22m[2massets/[22m[36mru-BQkxOHCe.js                            [39m[1m[2m   53.20 kB[22m[1m[22m[2m │ gzip:  20.67 kB[22m
[2mdist/[22m[2massets/[22m[36moverlayscrollbars-CiKU261J.js             [39m[1m[2m   57.95 kB[22m[1m[22m[2m │ gzip:  25.17 kB[22m
[2mdist/[22m[2massets/[22m[36men-Cv-MgCvq.js                            [39m[1m[2m   60.36 kB[22m[1m[22m[2m │ gzip:  19.84 kB[22m
[2mdist/[22m[2massets/[22m[36mde-DHBvIm9o.js                            [39m[1m[2m   62.46 kB[22m[1m[22m[2m │ gzip:  20.68 kB[22m
[2mdist/[22m[2massets/[22m[36mdefault.fragment-DN4yf4ZI.js              [39m[1m[2m   82.53 kB[22m[1m[22m[2m │ gzip:  15.92 kB[22m
[2mdist/[22m[2massets/[22m[36mdefault.fragment-CJrVJQDS.js              [39m[1m[2m   87.30 kB[22m[1m[22m[2m │ gzip:  15.67 kB[22m
[2mdist/[22m[2massets/[22m[36mJMuxerStream-BR8Lf0tH.js                  [39m[1m[2m  108.54 kB[22m[1m[22m[2m │ gzip:  33.21 kB[22m
[2mdist/[22m[2massets/[22m[36mJanusStreamer-Dcs_fdf6.js                 [39m[1m[2m  225.33 kB[22m[1m[22m[2m │ gzip:  63.17 kB[22m
[2mdist/[22m[2massets/[22m[36mHlsstreamer-LT1tHIyq.js                   [39m[1m[2m  367.26 kB[22m[1m[22m[2m │ gzip: 110.95 kB[22m
[2mdist/[22m[2massets/[22m[36mcodemirror-ZSHHXwGs.js                    [39m[1m[2m  408.15 kB[22m[1m[22m[2m │ gzip: 134.69 kB[22m
[2mdist/[22m[2massets/[22m[36mHeightmap-CbPNM0Ej.js                     [39m[1m[2m  446.28 kB[22m[1m[22m[2m │ gzip: 120.78 kB[22m
[2mdist/[22m[2massets/[22m[36mecharts-DzoUeqWp.js                       [39m[1m[33m  587.96 kB[39m[22m[2m │ gzip: 198.52 kB[22m
[2mdist/[22m[2massets/[22m[36mvuetify-BD4FQlry.js                       [39m[1m[33m1,110.13 kB[39m[22m[2m │ gzip: 292.64 kB[22m
[2mdist/[22m[2massets/[22m[36mViewer-DVYAEk59.js                        [39m[1m[33m1,847.99 kB[39m[22m[2m │ gzip: 448.93 kB[22m
[2mdist/[22m[2massets/[22m[36mindex-CpknIgmq.js                         [39m[1m[33m2,034.98 kB[39m[22m[2m │ gzip: 525.87 kB[22m
[33m
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.[39m
[32m✓ built in 35.93s[39m
Browserslist: browsers data (caniuse-lite) is 8 months old. Please run:
  npx update-browserslist-db@latest
  Why you should do it regularly: https://github.com/browserslist/update-db#readme

[36mPWA v1.2.0[39m
mode      [35mgenerateSW[39m
precache  [32m173 entries[39m [2m(9514.94 KiB)[22m
files generated
  [2mdist/sw.js[22m
  [2mdist/workbox-6730e12c.js[22m

> mainsail@2.17.0 build.zip
> cd ./dist && zip -r mainsail.zip ./ -x '**.DS_Store' ./ && cd ..

  adding: css/ (stored 0%)
  adding: css/themes/ (stored 0%)
  adding: css/themes/vzbot.css (deflated 16%)
  adding: img/ (stored 0%)
  adding: img/sidebar-background-light.svg (deflated 72%)
  adding: img/icons/ (stored 0%)
  adding: img/icons/favicon-16x16.png (stored 0%)
  adding: img/icons/mstile-150x150.png (deflated 6%)
  adding: img/icons/favicon-32x32.png (stored 0%)
  adding: img/icons/icon-192-maskable.png (deflated 0%)
  adding: img/icons/apple-touch-icon-180x180.png (stored 0%)
  adding: img/icons/safari-pinned-tab.svg (deflated 49%)
  adding: img/icons/icon-512-maskable.png (deflated 7%)
  adding: img/sidebar-background.svg (deflated 66%)
  adding: img/themes/ (stored 0%)
  adding: img/themes/sidebarLogo-vzbot.svg (deflated 47%)
  adding: img/themes/sidebarLogo-yumi.svg (deflated 56%)
  adding: img/themes/sidebarLogo-prusa.svg (deflated 60%)
  adding: img/themes/sidebarLogo-voron.svg (deflated 42%)
  adding: img/themes/sidebarLogo-multec.svg (deflated 41%)
  adding: img/themes/sidebarLogo-ldo.svg (deflated 42%)
  adding: img/themes/sidebarBackground-vzbot.png (deflated 0%)
  adding: img/themes/sidebarLogo-klipper.svg (deflated 55%)
  adding: img/themes/sidebarLogo-btt.svg (deflated 54%)
  adding: img/klipper.svg (deflated 54%)
  adding: img/logo.svg (deflated 37%)
  adding: sw.js (deflated 72%)
  adding: index.html (deflated 64%)
  adding: fonts/ (stored 0%)
  adding: fonts/roboto-regular.woff2 (stored 0%)
  adding: fonts/roboto-black.woff2 (stored 0%)
  adding: fonts/robotoMono-regular.woff (deflated 0%)
  adding: fonts/roboto-medium.woff2 (stored 0%)
  adding: fonts/roboto-thin.woff2 (stored 0%)
  adding: fonts/roboto-bold.woff2 (stored 0%)
  adding: fonts/roboto-light.woff2 (stored 0%)
  adding: config.json (deflated 45%)
  adding: manifest.webmanifest (deflated 52%)
  adding: workbox-6730e12c.js (deflated 66%)
  adding: release_info.json (deflated 22%)
  adding: assets/ (stored 0%)
  adding: assets/Hlsstreamer-LT1tHIyq.js (deflated 70%)
  adding: assets/kernelBlur.fragment-BChwTNr1.js (deflated 66%)
  adding: assets/default.vertex-CcbjUvcE.js (deflated 79%)
  adding: assets/basisTextureLoader-D73sPrtK.js (deflated 61%)
  adding: assets/cz-CvFrdRAO.js (deflated 66%)
  adding: assets/Codemirror-CGGt7agv.js (deflated 66%)
  adding: assets/line.vertex-BByBEITe.js (deflated 60%)
  adding: assets/cubemapToSphericalPolynomial-ByybCv08.js (deflated 55%)
  adding: assets/da-CDQuwckg.js (deflated 66%)
  adding: assets/index-DOW_gi1J.css (deflated 77%)
  adding: assets/WebrtcCameraStreamer-yZHlNmTi.js (deflated 60%)
  adding: assets/glowMapMerge.fragment-C_pRkCEG.js (deflated 53%)
  adding: assets/bakedVertexAnimation-4EsPuKdv.js (deflated 81%)
  adding: assets/envTextureLoader-DvV3BeS8.js (deflated 59%)
  adding: assets/kernelBlur.fragment-C3UIVtdL.js (deflated 69%)
  adding: assets/zh_TW-BiL12nRY.js (deflated 62%)
  adding: assets/meshUboDeclaration-CiQH4Nrv.js (deflated 43%)
  adding: assets/ddsTextureLoader-DHtVO0nw.js (deflated 53%)
  adding: assets/WebcamNozzleCrosshair-DPA1oXCy.js (deflated 51%)
  adding: assets/WebrtcMediaMTX-CKI2hlYR.js (deflated 60%)
  adding: assets/color.vertex-DGlh44p4.js (deflated 54%)
  adding: assets/Heightmap-CpnWqGHX.css (deflated 46%)
  adding: assets/glowMapGeneration.fragment-B9u2vcL6.js (deflated 67%)
  adding: assets/echarts-DzoUeqWp.js (deflated 66%)
  adding: assets/fogFragment-b8R0vCU2.js (deflated 56%)
  adding: assets/glowMapMerge.vertex-S7TrybPr.js (deflated 40%)
  adding: assets/postprocess.vertex-QwV_wQfa.js (deflated 42%)
  adding: assets/overlayscrollbars-BJn_P54_.css (deflated 77%)
  adding: assets/line.fragment-D4K-0R6U.js (deflated 47%)
  adding: assets/line.fragment-CL-ClIq2.js (deflated 40%)
  adding: assets/zh-B7S78EIg.js (deflated 64%)
  adding: assets/virtual_pwa-register-7QtbIe2t.js (deflated 41%)
  adding: assets/clipPlaneFragment-BGxauOiu.js (deflated 73%)
  adding: assets/en-Cv-MgCvq.js (deflated 67%)
  adding: assets/es-BsGSvpaW.js (deflated 67%)
  adding: assets/fr-CBN_6kdk.js (deflated 68%)
  adding: assets/overlayscrollbars-CiKU261J.js (deflated 57%)
  adding: assets/sk-B303QlGc.js (deflated 50%)
  adding: assets/MjpegstreamerAdaptive-BHk15LJJ.js (deflated 63%)
  adding: assets/fxaa.vertex-DWxAxM9l.js (deflated 60%)
  adding: assets/ko-DvMVVTO3.js (deflated 67%)
  adding: assets/Uv4lMjpeg-D1cEKtzw.js (deflated 57%)
  adding: assets/vertexColorMixing-DZyQZAeV.js (deflated 55%)
  adding: assets/Mjpegstreamer-CZYXtC7T.js (deflated 60%)
  adding: assets/color.fragment-BKhB8qFg.js (deflated 53%)
  adding: assets/default.fragment-CJrVJQDS.js (deflated 82%)
  adding: assets/bonesVertex-BJsVL_I_.js (deflated 80%)
  adding: assets/hdrTextureLoader-C7yzGa2C.js (deflated 52%)
  adding: assets/WebrtcGo2rtc-ycK71tfR.js (deflated 59%)
  adding: assets/morphTargetsVertex-uTSclvZE.js (deflated 74%)
  adding: assets/glowMapMerge.fragment-VtnO_VND.js (deflated 49%)
  adding: assets/pass.fragment-BBGK6O1l.js (deflated 32%)
  adding: assets/logDepthFragment-DTlpatAl.js (deflated 17%)
  adding: assets/logDepthVertex-Cj1b4f10.js (deflated 28%)
  adding: assets/mainUVVaryingDeclaration-BEhf1iLL.js (deflated 68%)
  adding: assets/WebcamNozzleCrosshair-ic6H6w5D.css (deflated 49%)
  adding: assets/HtmlVideo-CDKYMtyR.js (deflated 48%)
  adding: assets/HtmlIframe-wdueZHHk.js (deflated 48%)
  adding: assets/line.vertex-DiwwpGpZ.js (deflated 58%)
  adding: assets/color.vertex-CWyJMJsO.js (deflated 57%)
  adding: assets/Heightmap-CbPNM0Ej.js (deflated 73%)
  adding: assets/nl-C3ju2IW6.js (deflated 66%)
  adding: assets/glowMapMerge.vertex-De0bZc6q.js (deflated 38%)
  adding: assets/kernelBlur.vertex-GdTqCOpC.js (deflated 49%)
  adding: assets/WebrtcMediaMTX-B5-Yoyes.css (deflated 2%)
  adding: assets/clipPlaneVertex-Cm783hJI.js (deflated 75%)
  adding: assets/exrTextureLoader-SXZi-7VF.js (deflated 62%)
  adding: assets/logDepthDeclaration-D_H16P16.js (deflated 12%)
  adding: assets/workbox-window.prod.es5-BiUm-Zq1.js (deflated 59%)
  adding: assets/glowMapGeneration.vertex-BhiqkVcA.js (deflated 67%)
  adding: assets/uk-Pa8Qqtyo.js (deflated 72%)
  adding: assets/MjpegstreamerAdaptive-XhKyIuw0.css (deflated 35%)
  adding: assets/de-DHBvIm9o.js (deflated 67%)
  adding: assets/mainUVVaryingDeclaration-B8zhK2k5.js (deflated 57%)
  adding: assets/vuetify-BSwS9o2d.css (deflated 88%)
  adding: assets/helperFunctions-BuxhDd1e.js (deflated 69%)
  adding: assets/JMuxerStream-Ghy5S_h3.css (stored 0%)
  adding: assets/Viewer-DhDSIvud.css (deflated 53%)
  adding: assets/hu-Brwg4WkO.js (deflated 66%)
  adding: assets/fxaa.fragment-DTfPbW47.js (deflated 70%)
  adding: assets/kernelBlurVaryingDeclaration-DEp5Z2ny.js (deflated 7%)
  adding: assets/Mjpegstreamer-DqaKUdZ_.css (deflated 34%)
  adding: assets/se-Cn9Sb-Ng.js (deflated 66%)
  adding: assets/dds-BRUIW4jb.js (deflated 63%)
  adding: assets/kernelBlur.vertex-UxMCK5re.js (deflated 46%)
  adding: assets/morphTargetsVertex-BTVnpJFA.js (deflated 72%)
  adding: assets/JMuxerStream-BR8Lf0tH.js (deflated 70%)
  adding: assets/Viewer-DVYAEk59.js (deflated 76%)
  adding: assets/rgbdDecode.fragment-D8T067Yj.js (deflated 38%)
  adding: assets/ktxTextureLoader-gS5OO7iY.js (deflated 70%)
  adding: assets/vertexColorMixing-CvDooCuG.js (deflated 37%)
  adding: assets/codemirror-ZSHHXwGs.js (deflated 67%)
  adding: assets/glowBlurPostProcess.fragment-B7uZ3loo.js (deflated 54%)
  adding: assets/vuetify-BD4FQlry.js (deflated 74%)
  adding: assets/pass.fragment-BN3--opx.js (deflated 39%)
  adding: assets/kernelBlurVaryingDeclaration-C0qnyMq_.js (deflated 8%)
  adding: assets/WebrtcCameraStreamer-BRNlGQUz.css (deflated 2%)
  adding: assets/color.fragment-B7TjRvpL.js (deflated 51%)
  adding: assets/it-ClwfbRf6.js (deflated 68%)
  adding: assets/JanusStreamer-BRNQ5Tpp.css (deflated 2%)
  adding: assets/ru-BQkxOHCe.js (deflated 74%)
  adding: assets/glowMapGeneration.vertex-BxIwf4o2.js (deflated 69%)
  adding: assets/index-CpknIgmq.js (deflated 74%)
  adding: assets/glowMapGeneration.fragment-Dufs76Lu.js (deflated 62%)
  adding: assets/pl-CWhqMIU7.js (deflated 66%)
  adding: assets/pt-xi-NpSA_.js (deflated 67%)
  adding: assets/rgbdDecode.fragment-PLXOyizj.js (deflated 35%)
  adding: assets/tgaTextureLoader-CHX-mtG0.js (deflated 61%)
  adding: assets/fxaa.fragment-ICUQsw2C.js (deflated 73%)
  adding: assets/fxaa.vertex-F6xOLwWl.js (deflated 67%)
  adding: assets/JanusStreamer-Dcs_fdf6.js (deflated 72%)
  adding: assets/tr-zOmnN4My.js (deflated 66%)
  adding: assets/default.fragment-DN4yf4ZI.js (deflated 81%)
  adding: assets/glowBlurPostProcess.fragment-DG4cUbiz.js (deflated 49%)
  adding: assets/ja-DAsdMgq-.js (deflated 69%)
  adding: assets/WebrtcGo2rtc-Bsaeny4h.css (deflated 2%)
  adding: assets/default.vertex-BBW3X3T0.js (deflated 77%)
  adding: .version (stored 0%)
npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'start-server-and-test@3.0.11',
npm warn EBADENGINE   required: { node: '^22 || >=24' },
npm warn EBADENGINE   current: { node: 'v20.20.2', npm: '10.8.2' }
npm warn EBADENGINE }
npm warn deprecated inflight@1.0.6: This module is not supported, and leaks memory. Do not use it. Check out lru-cache if you want a good and tested way to coalesce async requests by a key value, which is much more comprehensive and powerful.
npm warn deprecated glob@8.1.0: Old versions of glob are not supported, and contain widely publicized security vulnerabilities, which have been fixed in the current version. Please update. Support for old versions may be purchased (at exorbitant rates) by contacting i@izs.me
npm warn deprecated glob@7.2.3: Old versions of glob are not supported, and contain widely publicized security vulnerabilities, which have been fixed in the current version. Please update. Support for old versions may be purchased (at exorbitant rates) by contacting i@izs.me
npm warn deprecated source-map@0.8.0-beta.0: The work that was done in this beta branch won't be included in future versions
npm warn deprecated vue-i18n@8.28.2: v9 and v10 no longer supported. please migrate to v11. about maintenance status, see https://vue-i18n.intlify.dev/guide/maintenance.html
npm warn deprecated glob@11.1.0: Old versions of glob are not supported, and contain widely publicized security vulnerabilities, which have been fixed in the current version. Please update. Support for old versions may be purchased (at exorbitant rates) by contacting i@izs.me
npm warn deprecated vue@2.7.16: Vue 2 has reached EOL and is no longer actively maintained. See https://v2.vuejs.org/eol/ for more details.

added 863 packages in 23s

/home/runner/work/_temp/mainsail-build-work/v2.18.2/src/components/mixins/dashboard.ts
  19:5  error  'mdiHistory' is defined but never used  @typescript-eslint/no-unused-vars

✖ 1 problem (1 error, 0 warnings)

HEAD is now at 2967f6b build: launch cumulative v0.8 via validation
Removing .github/workflows/build-v08.yml
Removing build/finalize-v08.sh
Removing build/v08-delete-paths.txt
Removing docs/HEALTH_TIMELINE.md
Removing docs/SMART_MAINTENANCE.md
Removing docs/TOOL_REGISTRY.md
Removing mainsail/mainsail-v2.17.0-v0.8.0.patch
Removing mainsail/mainsail-v2.18.2-v0.8.0.patch
Removing mainsail/src/components/klippertools/CalibrationCenterTool.vue
Removing mainsail/src/components/klippertools/HealthTimelineTool.vue
Removing mainsail/src/components/klippertools/ToolRegistryTool.vue
Removing mainsail/src/components/panels/CalibrationCenterPanel.vue
Removing mainsail/src/components/panels/HealthTimelinePanel.vue
Removing mainsail/src/components/panels/ToolRegistryPanel.vue
Removing scripts/build-mainsail-v0.8.0.sh
Removing tests/test_release_metadata.py
```
