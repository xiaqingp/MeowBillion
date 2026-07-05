import { fetchMergeCandidates, mergeTransactionsApi } from './api.js';
import { formatCurrency } from './utils.js';

export async function loadMergeCandidates(legacyId) {
    const container = document.getElementById(`merge-candidates-${legacyId}`);
    if (!container) return;
    
    try {
        const candidates = await fetchMergeCandidates(legacyId);
        if (candidates.error) {
            container.innerHTML = `<span class="text-danger">加载候选失败: ${candidates.error}</span>`;
            return;
        }
        if (candidates.length === 0) {
            container.innerHTML = `<span style="color:var(--text-muted); font-size:11px;">暂无相近的未对账 Plaid 交易候选 (在前后 15 天内)</span>`;
            return;
        }
        
        let html = `<ul style="list-style:none; padding:0; display:flex; flex-direction:column; gap:8px; margin: 8px 0 0 0;">`;
        candidates.forEach(c => {
            const statusTag = c.reviewed === 1 
                ? '<span style="background-color: var(--color-success-glow); color: var(--color-success); font-size:9px; padding:2px 4px; border-radius:4px; font-weight:700;">已对账</span>' 
                : '<span style="background-color: var(--color-warning-glow); color: var(--color-warning); font-size:9px; padding:2px 4px; border-radius:4px; font-weight:700;">待对账</span>';
            const diffDaysText = c.date_diff === 0 ? "同一天" : `相差 ${c.date_diff} 天`;
            
            html += `
                <li style="display:flex; justify-content:space-between; align-items:center; background-color:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border-color);" onclick="event.stopPropagation()">
                    <span style="color: var(--text-primary);">
                        <strong>${c.date}</strong> - <span style="color:var(--text-secondary);">${c.merchant}</span> (${c.account_name}) 
                        <strong class="${c.direction === 'outflow' ? 'amount-expense' : 'amount-income'}" style="margin-left:8px;">
                            ${c.direction === 'outflow' ? '-' : '+'}${formatCurrency(c.amount)}
                        </strong>
                        <span style="margin-left:12px; font-size:11px; color: var(--text-muted);">${diffDaysText}</span>
                        <span style="margin-left:8px;">${statusTag}</span>
                    </span>
                    <button class="btn btn-primary" style="height:26px; padding:0 8px; font-size:11px; background-color:var(--color-primary); color:white; border:none; border-radius:4px; cursor:pointer;" onclick="executeManualMerge('${legacyId}', '${c.transaction_id}', event)">
                        链接合并
                    </button>
                </li>
            `;
        });
        html += `</ul>`;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<span class="text-danger">请求候选异常: ${err.message}</span>`;
    }
}

export async function executeManualMerge(legacyId, plaidId, event) {
    if (event) event.stopPropagation();
    
    if (!confirm("您确定要将这笔 Legacy 历史交易合并到指定的 Plaid 流水中吗？\n\n这会用历史的手动分类/分账/备注覆盖 Plaid 交易，并自动删除此笔 Legacy 交易记录。")) {
        return;
    }
    
    try {
        const res = await mergeTransactionsApi(legacyId, plaidId);
        if (res.status === "success") {
            alert("合并成功！");
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("合并失败: " + res.error);
        }
    } catch (err) {
        console.error("Merge error:", err);
        alert("无法提交合并请求：" + err.message);
    }
}

export async function executePreciseMerge(legacyId, event) {
    if (event) event.stopPropagation();
    
    const plaidIdInput = document.getElementById(`manual-plaid-id-${legacyId}`);
    if (!plaidIdInput) return;
    
    const plaidId = plaidIdInput.value.trim();
    if (!plaidId) {
        alert("请输入目标 Plaid 交易 ID！");
        return;
    }
    
    if (!confirm(`您确定要将这笔 Legacy 历史交易合并到 Plaid 交易 ID [${plaidId}] 中吗？\n\n这会用历史的手动分类/分账/备注覆盖该 Plaid 交易，并自动删除此笔 Legacy 交易记录。`)) {
        return;
    }
    
    try {
        const res = await mergeTransactionsApi(legacyId, plaidId);
        if (res.status === "success") {
            alert("合并成功！");
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("合并失败: " + res.error);
        }
    } catch (err) {
        console.error("Merge error:", err);
        alert("无法提交合并请求：" + err.message);
    }
}
