export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 50;

export const PASSWORD_RULE_MESSAGE = `Password must be ${PASSWORD_MIN_LENGTH}-${PASSWORD_MAX_LENGTH} characters and include at least two of numbers, letters, and symbols.`;

/**
 * 密码正则（密码格式应为 8-50 位数字、字母、符号的任意两种组合）
 *
 * 基于 pure-admin 默认规则扩展最大长度到 50，避免与后端/创建用户规则不一致。
 */
export const REGEXP_PWD =
  /^(?![0-9]+$)(?![a-z]+$)(?![A-Z]+$)(?!([^(0-9a-zA-Z)]|[()])+$)(?!^.*[\u4E00-\u9FA5].*$)([^(0-9a-zA-Z)]|[()]|[a-z]|[A-Z]|[0-9]){8,50}$/;

export function isStrongPassword(password: string): boolean {
  return REGEXP_PWD.test(password);
}
