import fs from 'fs';
import path from 'path';

var EventType = /* @__PURE__ */ ((EventType2) => {
  EventType2["META"] = "meta_event";
  EventType2["REQUEST"] = "request";
  EventType2["NOTICE"] = "notice";
  EventType2["MESSAGE"] = "message";
  EventType2["MESSAGE_SENT"] = "message_sent";
  return EventType2;
})(EventType || {});

let startTime = Date.now();
let logger = null;
let currentConfig = {
  prefix: "#napcat",
  enableReply: true,
  description: "这是一个内置插件的配置示例"
};
let plugin_config_ui = [];
const plugin_init = async (ctx) => {
  logger = ctx.logger;
  logger.info("NapCat 内置插件已初始化");
  plugin_config_ui = ctx.NapCatConfig.combine(
    ctx.NapCatConfig.html('<div style="padding: 10px; background: rgba(0,0,0,0.05); border-radius: 8px;"><h3>👋 Welcome to NapCat Builtin Plugin</h3><p>This is a demonstration of the plugin configuration interface.</p></div>'),
    ctx.NapCatConfig.text("prefix", "Command Prefix", "#napcat", "The prefix to trigger the version info command"),
    ctx.NapCatConfig.boolean("enableReply", "Enable Reply", true, "Switch to enable or disable the reply functionality"),
    ctx.NapCatConfig.select("theme", "Theme Selection", [
      { label: "Light Mode", value: "light" },
      { label: "Dark Mode", value: "dark" },
      { label: "Auto", value: "auto" }
    ], "light", "Select a theme for the response (Demo purpose only)"),
    ctx.NapCatConfig.multiSelect("features", "Enabled Features", [
      { label: "Version Info", value: "version" },
      { label: "Status Report", value: "status" },
      { label: "Debug Log", value: "debug" }
    ], ["version"], "Select features to enable"),
    ctx.NapCatConfig.text("description", "Description", "这是一个内置插件的配置示例", "A multi-line text area for notes")
  );
  try {
    if (fs.existsSync(ctx.configPath)) {
      const savedConfig = JSON.parse(fs.readFileSync(ctx.configPath, "utf-8"));
      Object.assign(currentConfig, savedConfig);
    }
  } catch (e) {
    logger?.warn("Failed to load config", e);
  }
};
const plugin_get_config = async () => {
  return currentConfig;
};
const plugin_set_config = async (ctx, config) => {
  currentConfig = config;
  if (ctx && ctx.configPath) {
    try {
      const configPath = ctx.configPath;
      const configDir = path.dirname(configPath);
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      fs.writeFileSync(configPath, JSON.stringify(config, null, 2), "utf-8");
    } catch (e) {
      logger?.error("Failed to save config", e);
      throw e;
    }
  }
};
const plugin_onmessage = async (_ctx, event) => {
  if (currentConfig.enableReply === false) {
    return;
  }
  const prefix = currentConfig.prefix || "#napcat";
  if (event.post_type !== EventType.MESSAGE || !event.raw_message.startsWith(prefix)) {
    return;
  }
  try {
    const versionInfo = await getVersionInfo(_ctx.actions, _ctx.adapterName, _ctx.pluginManager.config);
    if (!versionInfo) return;
    const message = formatVersionMessage(versionInfo);
    await sendMessage(_ctx.actions, event, message, _ctx.adapterName, _ctx.pluginManager.config);
    logger?.info("已回复版本信息");
  } catch (error) {
    logger?.error("处理消息时发生错误:", error);
  }
};
async function getVersionInfo(actions, adapter, config) {
  if (!actions) return null;
  try {
    const data = await actions.call("get_version_info", void 0, adapter, config);
    return {
      appName: data.app_name,
      appVersion: data.app_version,
      protocolVersion: data.protocol_version
    };
  } catch (error) {
    logger?.error("获取版本信息失败:", error);
    return null;
  }
}
function formatUptime(ms) {
  const seconds = Math.floor(ms / 1e3);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) {
    return `${days}天 ${hours % 24}小时 ${minutes % 60}分钟`;
  } else if (hours > 0) {
    return `${hours}小时 ${minutes % 60}分钟`;
  } else if (minutes > 0) {
    return `${minutes}分钟 ${seconds % 60}秒`;
  } else {
    return `${seconds}秒`;
  }
}
function formatVersionMessage(info) {
  const uptime = Date.now() - startTime;
  return `NapCat 信息
版本: ${info.appVersion}
平台: ${process.platform}${process.arch === "x64" ? " (64-bit)" : ""}
运行时间: ${formatUptime(uptime)}`;
}
async function sendMessage(actions, event, message, adapter, config) {
  const params = {
    message,
    message_type: event.message_type,
    ...event.message_type === "group" && event.group_id ? { group_id: String(event.group_id) } : {},
    ...event.message_type === "private" && event.user_id ? { user_id: String(event.user_id) } : {}
  };
  try {
    await actions.call("send_msg", params, adapter, config);
  } catch (error) {
    logger?.error("发送消息失败:", error);
  }
}

export { plugin_config_ui, plugin_get_config, plugin_init, plugin_onmessage, plugin_set_config };
