// 后端时间均为 UTC 字符串（'YYYY-MM-DD HH:MM:SS'，datetime.utcnow 存储），展示前转本地时区
export function formatLocalTime(s) {
  if (!s) return '—';
  const d = new Date(s.replace(' ', 'T') + 'Z'); // 字符串按 UTC 解析
  if (isNaN(d.getTime())) return s;
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
