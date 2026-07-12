const {
  withAndroidManifest,
  withAppBuildGradle,
  withGradleProperties,
  withDangerousMod,
} = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

const MARKER = '// MeowBillion local release signing';
const launcherForeground = `<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="24" android:viewportHeight="24">
  <group android:scaleX="0.62" android:scaleY="0.62" android:translateX="4.56" android:translateY="4.56">
    <path android:fillColor="@android:color/transparent" android:pathData="M12,5c0.67,0 1.35,0.09 2,0.26c1.78,-2 5.03,-2.84 6.42,-2.26c1.4,0.58 -0.42,7 -0.42,7c0.57,1.07 1,2.24 1,3.44C21,17.9 16.97,21 12,21s-9,-3.1 -9,-7.56c0,-1.25 0.5,-2.4 1,-3.44c0,0 -1.89,-6.42 -0.5,-7c1.39,-0.58 4.72,0.23 6.5,2.23A9.04,9.04 0,0 1,12 5Z" android:strokeColor="#FFFFFF" android:strokeLineCap="round" android:strokeLineJoin="round" android:strokeWidth="2" />
    <path android:fillColor="@android:color/transparent" android:pathData="M8,14v0.5M16,14v0.5M11.25,16.25h1.5L12,17l-0.75,-0.75Z" android:strokeColor="#FFFFFF" android:strokeLineCap="round" android:strokeLineJoin="round" android:strokeWidth="2" />
  </group>
</vector>`;
const launcherIcon = `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@color/iconBackground" />
  <foreground android:drawable="@drawable/meowbillion_launcher_foreground" />
</adaptive-icon>`;
const splash = `<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
  <item android:drawable="@color/iconBackground" />
  <item android:drawable="@drawable/meowbillion_launcher_foreground" android:gravity="center" />
</layer-list>`;

module.exports = function withMeowBillionAndroid(config) {
  config = withAndroidManifest(config, (androidConfig) => {
    androidConfig.modResults.manifest.application[0].$['android:usesCleartextTraffic'] = 'true';
    return androidConfig;
  });

  config = withGradleProperties(config, (androidConfig) => {
    const property = androidConfig.modResults.find((item) => item.type === 'property' && item.key === 'reactNativeArchitectures');
    if (property) {
      property.value = 'arm64-v8a,x86_64';
    } else {
      androidConfig.modResults.push({ type: 'property', key: 'reactNativeArchitectures', value: 'arm64-v8a,x86_64' });
    }
    return androidConfig;
  });

  config = withAppBuildGradle(config, (androidConfig) => {
    if (androidConfig.modResults.contents.includes(MARKER)) {
      return androidConfig;
    }
    const properties = "def meowBillionReleasePropertiesFile = new File(System.getProperty('user.home'), '.meowbillion/android-release.properties')\ndef meowBillionReleaseProperties = new Properties()\nif (meowBillionReleasePropertiesFile.exists()) {\n    meowBillionReleasePropertiesFile.withInputStream { meowBillionReleaseProperties.load(it) }\n}\n";
    androidConfig.modResults.contents = androidConfig.modResults.contents.replace(
      'def enableMinifyInReleaseBuilds = (findProperty(\'android.enableMinifyInReleaseBuilds\') ?: false).toBoolean()\n',
      `def enableMinifyInReleaseBuilds = (findProperty('android.enableMinifyInReleaseBuilds') ?: false).toBoolean()\n${properties}`,
    );
    androidConfig.modResults.contents += `\n${MARKER}\nif (meowBillionReleasePropertiesFile.exists()) {\n    def meowBillionReleaseSigningConfig = android.signingConfigs.findByName('release') ?: android.signingConfigs.create('release')\n    meowBillionReleaseSigningConfig.storeFile = file(meowBillionReleaseProperties.getProperty('storeFile'))\n    meowBillionReleaseSigningConfig.storePassword = meowBillionReleaseProperties.getProperty('storePassword')\n    meowBillionReleaseSigningConfig.keyAlias = meowBillionReleaseProperties.getProperty('keyAlias')\n    meowBillionReleaseSigningConfig.keyPassword = meowBillionReleaseProperties.getProperty('keyPassword')\n    android.buildTypes.getByName('release').signingConfig = meowBillionReleaseSigningConfig\n}\n`;
    return androidConfig;
  });

  config = withDangerousMod(config, [
    'android',
    async (androidConfig) => {
      const res = path.join(androidConfig.modRequest.platformProjectRoot, 'app', 'src', 'main', 'res');
      fs.writeFileSync(path.join(res, 'drawable', 'meowbillion_launcher_foreground.xml'), launcherForeground);
      fs.writeFileSync(path.join(res, 'drawable', 'meowbillion_splash.xml'), splash);
      fs.writeFileSync(path.join(res, 'mipmap-anydpi-v26', 'ic_launcher.xml'), launcherIcon);
      fs.writeFileSync(path.join(res, 'mipmap-anydpi-v26', 'ic_launcher_round.xml'), launcherIcon);

      const colorsPath = path.join(res, 'values', 'colors.xml');
      const stylesPath = path.join(res, 'values', 'styles.xml');
      fs.writeFileSync(colorsPath, fs.readFileSync(colorsPath, 'utf8').replace(/<color name="iconBackground">[^<]*<\/color>/, '<color name="iconBackground">#0ABAB5</color>'));
      fs.writeFileSync(stylesPath, fs.readFileSync(stylesPath, 'utf8').replace('@drawable/splashscreen_logo', '@drawable/meowbillion_splash'));
      return androidConfig;
    },
  ]);

  return config;
};
