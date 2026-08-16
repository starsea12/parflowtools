// 表单校验工具

/**
 * 密码规则:8-16 位,且必须同时包含字母和数字。
 * 仅用于"设置新密码"场景(注册/改密/重置);登录表单不套用,以兼容旧规则的存量密码。
 */
export function validatePassword(rule, value, callback) {
  if (!value) {
    callback(new Error('请输入密码'));
  } else if (value.length < 8 || value.length > 16) {
    callback(new Error('密码长度需为8-16位'));
  } else if (!/[A-Za-z]/.test(value) || !/[0-9]/.test(value)) {
    callback(new Error('密码必须同时包含字母和数字'));
  } else {
    callback();
  }
}
