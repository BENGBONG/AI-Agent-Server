# 信用管家：逐 Skill 详细设计与业务填写入口

日期：2026-10-23。版本：v1 详细设计草案。

已将 9 类业务 Skill 和 3 类公共 Skill 分别整理为入口草案、详细设计和规则填写表。所有文件只在 docs 下，不在运行 Skill 库；没有导入、绑定、注册新工具或修改现有 Agent。目录中的 SKILL.md 是可审查入口草案，不是已发布包。

## 你怎么检查和补充

1. 先看 [共同约定与 8 项全局规则](00-common-design-and-rules.md)，填写业务范围、时效、动作与资料保留等跨 Skill 口径。
2. 按下表逐项打开“详细设计”，检查职责、字段、处理步骤与分支、输出、依赖和验收场景。
3. 在对应“业务规则”文件里替换 **你的规则：【待填写】**。建议补适用范围、例外、来源及一正一反样例；或在聊天按编号回复，例如 `B01-R01：……`。
4. 将状态改为“已填写待审”，复核后再“已确认”。不适用写原因，不用硬填一条规则。填写不是自动发布，实施时仍需相应工具和验收。

业务规则答案只在各自填写表维护一份；本索引和详细设计仅引用编号。没有待你决定的内容不刻意留空；已有明确需求直接作为设计约定。

## 逐项目录

| 编号 | 职责 | 详细设计 | 入口草案 | 业务规则 |
|---|---|---|---|---|
| B01 | 账单管理 | [credit-bill-management](B01-credit-bill-management/DESIGN.md) | [入口](B01-credit-bill-management/SKILL.md) | [填写 7 项](B01-credit-bill-management/references/business-rules.md) |
| B02 | 还款规划 | [credit-repayment-planning](B02-credit-repayment-planning/DESIGN.md) | [入口](B02-credit-repayment-planning/SKILL.md) | [填写 7 项](B02-credit-repayment-planning/references/business-rules.md) |
| B03 | 费用分析 | [credit-cost-analysis](B03-credit-cost-analysis/DESIGN.md) | [入口](B03-credit-cost-analysis/SKILL.md) | [填写 8 项](B03-credit-cost-analysis/references/business-rules.md) |
| B04 | 还款支持 | [credit-repayment-support](B04-credit-repayment-support/DESIGN.md) | [入口](B04-credit-repayment-support/SKILL.md) | [填写 6 项](B04-credit-repayment-support/references/business-rules.md) |
| B05 | 机构联系 | [credit-lender-contact](B05-credit-lender-contact/DESIGN.md) | [入口](B05-credit-lender-contact/SKILL.md) | [填写 6 项](B05-credit-lender-contact/references/business-rules.md) |
| B06 | 协商辅助 | [credit-negotiation-assistance](B06-credit-negotiation-assistance/DESIGN.md) | [入口](B06-credit-negotiation-assistance/SKILL.md) | [填写 7 项](B06-credit-negotiation-assistance/references/business-rules.md) |
| B07 | 投诉辅助 | [credit-complaint-assistance](B07-credit-complaint-assistance/DESIGN.md) | [入口](B07-credit-complaint-assistance/SKILL.md) | [填写 6 项](B07-credit-complaint-assistance/references/business-rules.md) |
| B08 | 征信解读 | [credit-report-interpretation](B08-credit-report-interpretation/DESIGN.md) | [入口](B08-credit-report-interpretation/SKILL.md) | [填写 7 项](B08-credit-report-interpretation/references/business-rules.md) |
| B09 | 产品匹配 | [credit-loan-matching](B09-credit-loan-matching/DESIGN.md) | [入口](B09-credit-loan-matching/SKILL.md) | [填写 8 项](B09-credit-loan-matching/references/business-rules.md) |
| C01 | 信息采集 | [credit-information-intake](C01-credit-information-intake/DESIGN.md) | [入口](C01-credit-information-intake/SKILL.md) | [填写 6 项](C01-credit-information-intake/references/business-rules.md) |
| C02 | 材料核验 | [credit-evidence-review](C02-credit-evidence-review/DESIGN.md) | [入口](C02-credit-evidence-review/SKILL.md) | [填写 6 项](C02-credit-evidence-review/references/business-rules.md) |
| C03 | 画像与记忆 | [credit-profile-memory](C03-credit-profile-memory/DESIGN.md) | [入口](C03-credit-profile-memory/SKILL.md) | [填写 7 项](C03-credit-profile-memory/references/business-rules.md) |

共 **12 个 Skill、8 项全局规则、81 项业务规则、72 个验收场景**。每个规则预留答案、范围/例外、来源/维护责任和正反样例。

## 单项详细设计包含什么

- 实际与规划的包结构，references / scripts / assets 的具体用途和读取时机。
- 输入字段、类型、必要条件、事实来源与校验；服务上下文统一说明。
- 分步骤处理与分支，每一步关联需要你补充的规则编号。
- 输出字段、合成结构例子、局部/等待/取消/完成条件。
- 现有工具和拟议能力的明确区分、主 Agent 跨 Skill 衔接。
- 用户拒绝、来源冲突、工具故障、缺规则、回执不明的处理。
- 正常、信息缺失、冲突及不应触发等 6 个验收场景。

## 审查顺序建议

先全局规则，再 B01 账单 → C01 采集 → C02 材料 → B02 规划 → B03 费用 → B04 还款支持；随后 B05 联系 → B06 协商 → B07 投诉；最后 C03 画像记忆 → B08 征信 → B09 匹配。你可以按自己熟悉的业务先填写，无需一次补完。

## 衔接与不重复定义

B01 维护账单事实，C02 负责候选与证据；C03 不另建第二本账。B02 决定计划流程，B03 定义费用分析流程，确定性计算能力可复用同一服务。B05 只查主体和渠道，B06/B07 各自组织协商与投诉材料；不把联系成功当案件成功。B08 解读报告，B09 只有明确融资意图才匹配。C01 按任务缺口收集，不能成为全套资料采集门槛。

所有需要确认的环节使用 get_user_choice。自由金额/日期/上传的专用交互尚待设计实现；没有时如实利用现有对话和附件入口，不能假装界面已支持。

## 设计完成后的动作

逐项讨论填写 → 消除跨 Skill 口径冲突 → 定稿对应 references 和入口 → 按工具依赖建设 → 用脱敏/合成场景验收 → 再选择导入与绑定。当前不自动推进实施，也不把示例费率、阈值、机构渠道或产品条件当业务规则。

总体分类来源：[Skill 体系设计 v1](../credit-manager-skills-design-v1.md)。最新细节以本目录为讨论入口。机器检查记录在 verification.json，结构索引在 catalog.json；均不是运行框架的配置或 manifest。
