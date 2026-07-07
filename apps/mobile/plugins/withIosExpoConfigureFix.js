/**
 * Expo prebuild plugin: keep iOS Podfile post_install workaround for
 * expo-configure-project.sh "Operation not permitted" (macOS provenance xattr).
 */
const { withPodfile } = require("@expo/config-plugins");
const {
  mergeContents,
} = require("@expo/config-plugins/build/utils/generateCode");

const TAG = "salareen-expo-configure-provenance-fix";

const PODFILE_SNIPPET = [
  "",
  "    # Xcode 15+/26: disable script sandboxing on Pod targets.",
  "    installer.pods_project.targets.each do |target|",
  "      target.build_configurations.each do |config|",
  "        config.build_settings['ENABLE_USER_SCRIPT_SANDBOXING'] = 'NO'",
  "      end",
  "    end",
  "    installer.pods_project.save",
  "",
  "    # macOS Sequoia: Node-written Pods scripts carry com.apple.provenance and",
  "    # Xcode fails with \"Operation not permitted\" when exec'ing expo-configure-project.sh.",
  "    pods_root = installer.sandbox.root.to_s",
  "    Dir.glob(File.join(pods_root, '**', '*.sh')).each do |script|",
  "      system('xattr', '-c', script) if File.file?(script)",
  "    end",
  "",
  "    require 'xcodeproj'",
  "    app_project_path = File.join(__dir__, 'Salareen.xcodeproj')",
  "    if File.directory?(app_project_path)",
  "      app_project = Xcodeproj::Project.open(app_project_path)",
  "      expo_shell = <<~'SCRIPT'",
  "        # This script configures Expo modules and generates the modules provider file.",
  "        # Workaround: cat script into bash -c to avoid macOS \"Operation not permitted\" on provenance xattr.",
  '        EXPO_CFG="${PODS_ROOT}/Target Support Files/Pods-${TARGET_NAME}/expo-configure-project.sh"',
  '        bash -l -c "$(cat "$EXPO_CFG")"',
  "      SCRIPT",
  "      app_project.targets.each do |target|",
  "        target.build_phases.each do |phase|",
  "          next unless phase.is_a?(Xcodeproj::Project::Object::PBXShellScriptBuildPhase)",
  "          next unless phase.name == '[Expo] Configure project'",
  "          phase.shell_script = expo_shell",
  "        end",
  "        target.build_configurations.each do |config|",
  "          config.build_settings['ENABLE_USER_SCRIPT_SANDBOXING'] = 'NO'",
  "        end",
  "      end",
  "      app_project.save",
  "      Pod::UI.puts('Patched [Expo] Configure project (cat|bash provenance workaround)'.green)",
  "    end",
].join("\n");

function withIosExpoConfigureFix(config) {
  return withPodfile(config, (cfg) => {
    const result = mergeContents({
      src: cfg.modResults.contents,
      newSrc: PODFILE_SNIPPET,
      tag: TAG,
      anchor: /installer\.target_installation_results\.pod_target_installation_results/,
      offset: 7,
      comment: "#",
    });
    if (result.didMerge || result.didClear) {
      cfg.modResults.contents = result.contents;
    }
    return cfg;
  });
}

module.exports = withIosExpoConfigureFix;
