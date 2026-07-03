var na=Object.defineProperty;var M=(e,t)=>()=>(e&&(t=e(e=0)),t);var Fr=(e,t)=>{for(var n in t)na(e,n,{get:t[n],enumerable:!0})};function ir(e){return e==="auto"?window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light":e}function kc(e){return e==="future"||e==="system"?"dark":e==="bare"?"light":["light","dark","auto"].includes(e)?e:"auto"}function ar(e){document.documentElement.setAttribute("data-theme",e);let t=Cc[e];if(t)for(let[n,r]of Object.entries(t))document.documentElement.style.setProperty(n,r)}function Co(e){document.querySelectorAll(".theme-switcher-btn").forEach(n=>{n.classList.toggle("active",n.dataset.themeMode===e)})}function lr(e){localStorage.setItem("theme-preference",e),ar(ir(e)),Co(e)}function ko(){let e=kc(localStorage.getItem("theme-preference")||"auto");localStorage.setItem("theme-preference",e),ar(ir(e)),Co(e);let t=document.getElementById("themeSwitcher");t&&t.addEventListener("click",n=>{let r=n.target.closest(".theme-switcher-btn");if(!r)return;let s=r.dataset.themeMode;s&&lr(s)}),window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>{(localStorage.getItem("theme-preference")||"auto")==="auto"&&ar(ir("auto"))})}var Cc,Io=M(()=>{Cc={light:{"--bg-base":"240 20% 97%","--bg-elevated":"0 0% 100%","--bg-glass":"0 0% 100% / 0.55","--bg-glass-hover":"0 0% 100% / 0.72","--bg-glass-active":"0 0% 100% / 0.85","--bg-surface":"220 14% 96%","--bg-surface-hover":"220 14% 93%","--bg-overlay":"220 20% 96% / 0.8","--border-glass":"0 0% 100% / 0.6","--border-subtle":"220 13% 91%","--border-focus":"221 83% 53%","--text-primary":"220 14% 10%","--text-secondary":"220 9% 43%","--text-tertiary":"220 9% 60%","--text-inverse":"0 0% 100%","--accent":"221 83% 53%","--accent-hover":"221 83% 47%","--accent-subtle":"221 83% 53% / 0.08","--accent-glow":"221 83% 53% / 0.15","--success":"142 71% 45%","--warning":"38 92% 50%","--danger":"0 72% 51%","--danger-subtle":"0 72% 51% / 0.08","--shadow-sm":"0 1px 2px hsl(220 14% 10% / 0.04), 0 1px 3px hsl(220 14% 10% / 0.03)","--shadow-md":"0 4px 6px hsl(220 14% 10% / 0.04), 0 2px 4px hsl(220 14% 10% / 0.03)","--shadow-lg":"0 10px 25px hsl(220 14% 10% / 0.06), 0 4px 10px hsl(220 14% 10% / 0.04)","--shadow-glass":"0 8px 32px hsl(220 14% 10% / 0.06), inset 0 1px 0 hsl(0 0% 100% / 0.6)","--blur-glass":"20px","--blur-bg":"40px","--gradient-mesh":"radial-gradient(ellipse at 20% 50%, hsl(221 83% 53% / 0.04) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, hsl(262 83% 58% / 0.04) 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, hsl(190 80% 50% / 0.03) 0%, transparent 50%)","--noise-opacity":"0.015","--tag-bg":"221 83% 53% / 0.08","--tag-text":"221 83% 40%","--scrollbar-track":"220 14% 96%","--scrollbar-thumb":"220 9% 82%","--code-bg":"220 14% 96%"},dark:{"--bg-base":"224 25% 8%","--bg-elevated":"224 22% 12%","--bg-glass":"224 22% 14% / 0.6","--bg-glass-hover":"224 22% 16% / 0.72","--bg-glass-active":"224 22% 18% / 0.85","--bg-surface":"224 20% 14%","--bg-surface-hover":"224 20% 18%","--bg-overlay":"224 25% 8% / 0.85","--border-glass":"224 15% 22% / 0.6","--border-subtle":"224 15% 20%","--border-focus":"217 91% 60%","--text-primary":"220 14% 95%","--text-secondary":"220 9% 65%","--text-tertiary":"220 9% 46%","--text-inverse":"220 14% 10%","--accent":"217 91% 60%","--accent-hover":"217 91% 67%","--accent-subtle":"217 91% 60% / 0.1","--accent-glow":"217 91% 60% / 0.12","--success":"142 71% 45%","--warning":"38 92% 50%","--danger":"0 72% 55%","--danger-subtle":"0 72% 55% / 0.1","--shadow-sm":"0 1px 2px hsl(0 0% 0% / 0.2), 0 1px 3px hsl(0 0% 0% / 0.15)","--shadow-md":"0 4px 6px hsl(0 0% 0% / 0.2), 0 2px 4px hsl(0 0% 0% / 0.15)","--shadow-lg":"0 10px 25px hsl(0 0% 0% / 0.3), 0 4px 10px hsl(0 0% 0% / 0.2)","--shadow-glass":"0 8px 32px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(0 0% 100% / 0.04)","--blur-glass":"20px","--blur-bg":"40px","--gradient-mesh":"radial-gradient(ellipse at 20% 50%, hsl(217 91% 60% / 0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, hsl(262 83% 58% / 0.05) 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, hsl(190 80% 50% / 0.04) 0%, transparent 50%)","--noise-opacity":"0.03","--tag-bg":"217 91% 60% / 0.12","--tag-text":"217 91% 72%","--scrollbar-track":"224 20% 12%","--scrollbar-thumb":"224 15% 26%","--code-bg":"224 20% 10%"}}});function dr(){try{let e=localStorage.getItem(cr);return e?JSON.parse(e):[]}catch(e){return console.error("Failed to load search history:",e),[]}}function Ic(e){try{localStorage.setItem(cr,JSON.stringify(e))}catch(t){console.error("Failed to save search history:",t)}}function To(e){let t=dr(),n={query:e.query,mode:e.mode,project:e.project,tool:e.tool,date:e.date,dateFrom:e.dateFrom,dateTo:e.dateTo,sortBy:e.sortBy,timestamp:new Date().toISOString()};if(t.length>0){let r=t[0];if(r.query===n.query&&r.mode===n.mode&&r.project===n.project&&r.tool===n.tool&&r.date===n.date)return}t.unshift(n),t.length>20&&(t.length=20),Ic(t),Ut()}function Ao(){localStorage.removeItem(cr),Ut()}function $o(){if(!document.getElementById("search"))return;let t=document.createElement("div");t.id="searchHistoryContainer",t.style.cssText=`
        position: relative;
        display: none;
        margin-top: 8px;
        background: hsl(var(--bg-elevated));
        border: 1px solid hsl(var(--border-glass));
        border-radius: 8px;
        padding: 8px;
        max-height: 400px;
        overflow-y: auto;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        z-index: 100;
    `;let n=document.querySelector(".search-controls");n&&n.parentNode.insertBefore(t,n.nextSibling);let r=document.createElement("button");r.id="historyToggle",r.textContent="\u{1F550} Recent Searches",r.style.cssText=`
        margin-top: 8px;
        padding: 6px 12px;
        background: hsl(var(--bg-surface));
        border: 1px solid hsl(var(--border-glass));
        border-radius: 6px;
        color: hsl(var(--text-primary));
        font-family: var(--font-sans);
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    `,r.onmouseover=()=>{r.style.background="hsl(var(--bg-elevated))"},r.onmouseout=()=>{r.style.background="hsl(var(--bg-surface))"},r.onclick=Tc,n&&n.parentNode.insertBefore(r,t),Ut()}function Tc(){let e=document.getElementById("searchHistoryContainer");if(!e)return;let t=e.style.display!=="none";e.style.display=t?"none":"block";let n=document.getElementById("historyToggle");n&&(n.textContent=t?"\u{1F550} Recent Searches":"\u2715 Close History"),t||Ut()}function Ut(){let e=document.getElementById("searchHistoryContainer");if(!e)return;let t=dr();if(t.length===0){e.innerHTML=`
            <div style="color: hsl(var(--text-tertiary)); font-size: 13px; text-align: center; padding: 16px;">
                No recent searches yet
            </div>
        `;return}let n=`
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid hsl(var(--border-subtle));">
            <div style="color: hsl(var(--text-primary)); font-weight: 500; font-size: 13px;">
                Recent Searches
            </div>
            <button onclick="window.clearSearchHistory()" style="
                background: transparent;
                border: none;
                color: hsl(var(--text-tertiary));
                font-size: 12px;
                cursor: pointer;
                padding: 4px 8px;
                border-radius: 4px;
                transition: all 0.2s;
            " onmouseover="this.style.background='hsl(var(--bg-surface))'" onmouseout="this.style.background='transparent'">
                Clear All
            </button>
        </div>
    `;t.forEach((r,s)=>{let o=new Date(r.timestamp),i=Ac(o),a=[];r.mode&&r.mode!=="hybrid"&&a.push(`mode: ${r.mode}`),r.project&&a.push(`project: ${r.project}`),r.tool&&a.push(`tool: ${r.tool}`),r.date&&r.date!=="all"&&a.push(`date: ${r.date}`);let l=a.length>0?a.join(", "):"no filters";n+=`
            <div class="history-entry" onclick="window.restoreSearchFromHistory(${s})" style="
                padding: 10px;
                margin-bottom: 4px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
                border: 1px solid transparent;
            " onmouseover="this.style.background='hsl(var(--bg-surface))'; this.style.borderColor='hsl(var(--border-glass))'" onmouseout="this.style.background='transparent'; this.style.borderColor='transparent'">
                <div style="color: hsl(var(--text-primary)); font-size: 14px; margin-bottom: 4px; font-weight: 500;">
                    ${r.query||'<em style="color: hsl(var(--text-tertiary));">(empty query)</em>'}
                </div>
                <div style="color: hsl(var(--text-tertiary)); font-size: 12px;">
                    ${l} \u2022 ${i}
                </div>
            </div>
        `}),e.innerHTML=n}function Lo(e){let t=dr();if(e<0||e>=t.length)return;let n=t[e];document.getElementById("search").value=n.query||"",document.getElementById("mode").value=n.mode||"hybrid",document.getElementById("project").value=n.project||"",document.getElementById("tool").value=n.tool||"",document.getElementById("date").value=n.date||"all",document.getElementById("sortBy").value=n.sortBy||"relevance",n.date==="custom"&&(document.getElementById("dateFrom").value=n.dateFrom||"",document.getElementById("dateTo").value=n.dateTo||"",window.toggleCustomDate&&window.toggleCustomDate());let r=document.getElementById("searchHistoryContainer");r&&(r.style.display="none");let s=document.getElementById("historyToggle");s&&(s.textContent="\u{1F550} Recent Searches"),window.search&&window.search()}function Ac(e){let t=Math.floor((new Date-e)/1e3);return t<60?"just now":t<3600?`${Math.floor(t/60)}m ago`:t<86400?`${Math.floor(t/3600)}h ago`:t<2592e3?`${Math.floor(t/86400)}d ago`:e.toLocaleDateString()}var cr,ur=M(()=>{cr="searchat_search_history"});function Ho(){return`
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" stroke-width="2"></rect>
            <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" stroke="currentColor" stroke-width="2"></path>
        </svg>
    `}function $c(){return`
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
    `}async function Mo(e,t){t.innerHTML='<div class="loading">Loading code blocks...</div>';try{let n=await fetch(`/api/conversation/${e}/code`);if(!n.ok){let l=await n.json().catch(()=>null),c=l&&l.detail?l.detail:"Failed to load code blocks";t.innerHTML=`<div style="color: hsl(var(--danger));">${c}</div>`;return}let r=await n.json();if(!r.code_blocks||r.code_blocks.length===0){t.innerHTML=`
                <div style="
                    text-align: center;
                    padding: 40px 20px;
                    color: hsl(var(--text-tertiary));
                ">
                    <div style="font-size: 48px; margin-bottom: 16px;">\u{1F4C4}</div>
                    <div style="font-size: 16px; margin-bottom: 8px;">No code blocks found</div>
                    <div style="font-size: 13px;">This conversation doesn't contain any code snippets</div>
                </div>
            `;return}let s={};r.code_blocks.forEach(l=>{s[l.language]||(s[l.language]=[]),s[l.language].push(l)});let o=Object.keys(s).sort(),i=o.map(l=>`${l} (${s[l].length})`).join(", "),a=`
            <div style="
                background: hsl(var(--bg-surface));
                padding: 16px;
                border-radius: 8px;
                margin-bottom: 20px;
                border: 1px solid hsl(var(--border-glass));
            ">
                <div style="font-size: 16px; font-weight: 500; color: hsl(var(--text-primary)); margin-bottom: 8px;">
                    \u{1F4CA} ${r.total_blocks} Code Block${r.total_blocks!==1?"s":""} Found
                </div>
                <div style="font-size: 13px; color: hsl(var(--text-tertiary));">
                    ${i}
                </div>
            </div>
        `;a+=`
            <div style="margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 8px;">
                <button class="lang-filter active" data-lang="all" style="
                    padding: 6px 12px;
                    background: hsl(var(--accent));
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    cursor: pointer;
                    font-family: var(--font-sans);
                ">
                    All (${r.total_blocks})
                </button>
        `,o.forEach(l=>{a+=`
                <button class="lang-filter" data-lang="${l}" style="
                    padding: 6px 12px;
                    background: hsl(var(--bg-surface));
                    color: hsl(var(--text-primary));
                    border: 1px solid hsl(var(--border-glass));
                    border-radius: 6px;
                    font-size: 13px;
                    cursor: pointer;
                    font-family: var(--font-sans);
                ">
                    ${l} (${s[l].length})
                </button>
            `}),a+="</div>",a+='<div id="codeBlocksContainer">',r.code_blocks.forEach((l,c)=>{let u=l.role==="user"?"user":"assistant",d=l.role==="user"?"USER":"ASSISTANT",f=l.language_source||"detected";a+=`
                <div class="code-block-item" data-language="${l.language}" data-language-source="${f}" style="
                    background: hsl(var(--bg-elevated));
                    border: 1px solid hsl(var(--border-glass));
                    border-radius: 8px;
                    margin-bottom: 16px;
                    overflow: hidden;
                ">
                    <div style="
                        background: hsl(var(--bg-surface));
                        padding: 10px 16px;
                        border-bottom: 1px solid hsl(var(--border-glass));
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="role-badge ${u}" style="
                                padding: 4px 8px;
                                border-radius: 4px;
                                font-size: 11px;
                                font-weight: 500;
                            ">
                                ${d}
                            </span>
                            <span style="
                                font-family: var(--font-mono);
                                font-size: 12px;
                                color: hsl(var(--text-primary));
                                background: hsl(var(--bg-elevated));
                                padding: 4px 8px;
                                border-radius: 4px;
                            ">
                                ${l.language}
                            </span>
                            <span style="font-size: 12px; color: hsl(var(--text-tertiary));">
                                ${l.lines} line${l.lines!==1?"s":""}
                            </span>
                        </div>
                        <button class="code-copy-trigger" type="button" data-copy-index="${c}" title="Copy code" aria-label="Copy code" style="
                            padding: 4px 8px;
                            background: transparent;
                            border: 1px solid hsl(var(--border-glass));
                            border-radius: 4px;
                            color: hsl(var(--text-primary));
                            cursor: pointer;
                            transition: all 0.2s;
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                        ">
                            ${Ho()}
                        </button>
                    </div>
                    <pre id="code-${c}" style="
                        margin: 0;
                        padding: 16px;
                        background: hsl(var(--code-bg));
                        overflow-x: auto;
                    "><code class="pygments" style="
                        font-family: var(--font-mono);
                        font-size: 13px;
                        line-height: 1.5;
                        color: hsl(var(--text-primary));
                    ">${Bc(l.code)}</code></pre>
                </div>
            `}),a+="</div>",t.innerHTML=a,await Bo(t,r.code_blocks,{mode:"fence"}),Lc(async()=>{await Bo(t,r.code_blocks,{mode:"guess"})}),t.querySelectorAll(".lang-filter").forEach(l=>{l.addEventListener("click",()=>{let c=l.dataset.lang;t.querySelectorAll(".lang-filter").forEach(u=>{u.classList.remove("active"),u.style.background="hsl(var(--bg-surface))",u.style.color="hsl(var(--text-primary))"}),l.classList.add("active"),l.style.background="hsl(var(--accent))",l.style.color="white",t.querySelectorAll(".code-block-item").forEach(u=>{c==="all"||u.dataset.language===c?u.style.display="block":u.style.display="none"})})}),t.querySelectorAll(".code-copy-trigger").forEach(l=>{l.addEventListener("click",()=>{let c=Number(l.dataset.copyIndex);fr(c,l)})}),window._codeBlocks=r.code_blocks}catch(n){t.innerHTML=`<div style="color: hsl(var(--danger));">Error: ${n.message}</div>`}}async function Bo(e,t,{mode:n}){let r=Array.from(e.querySelectorAll(".code-block-item")),s=[];for(let o=0;o<t.length;o++){let i=t[o],a=r[o];if(!i||!a)continue;let l=a.dataset.languageSource||i.language_source||"detected",c=String(i.language||"").toLowerCase(),u=l==="fence";n==="fence"&&!u||n==="guess"&&u||n==="guess"&&["plaintext","text","plain"].includes(c)||s.push({index:o,code:i.code,language:u?i.language:null,language_source:u?"fence":"detected"})}if(s.length!==0)try{let o=await fetch("/api/code/highlight",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({blocks:s.map(l=>({code:l.code,language:l.language,language_source:l.language_source}))})});if(!o.ok)return;let i=await o.json(),a=Array.isArray(i.results)?i.results:[];for(let l=0;l<s.length;l++){let c=s[l],u=a[l];if(!u||typeof u.html!="string")continue;let d=e.querySelector(`#code-${c.index}`),f=d?d.querySelector("code"):null;f&&(f.classList.add("pygments"),f.innerHTML=u.html)}}catch{return}}function Lc(e){if(typeof window.requestIdleCallback=="function"){window.requestIdleCallback(()=>{e()},{timeout:1500});return}setTimeout(()=>{e()},0)}function fr(e,t=null){if(!window._codeBlocks||!window._codeBlocks[e])return;let n=window._codeBlocks[e].code,r=t||document.querySelector(`.code-copy-trigger[data-copy-index="${e}"]`);r instanceof HTMLElement&&navigator.clipboard.writeText(n).then(()=>{r.innerHTML=$c(),r.style.background="hsl(var(--success))",r.style.color="white",r.style.borderColor="hsl(var(--success))",r.setAttribute("title","Copied"),r.setAttribute("aria-label","Copied"),setTimeout(()=>{r.innerHTML=Ho(),r.style.background="transparent",r.style.color="hsl(var(--text-primary))",r.style.borderColor="hsl(var(--border-glass))",r.setAttribute("title","Copy code"),r.setAttribute("aria-label","Copy code")},2e3)}).catch(s=>{console.error("Failed to copy code:",s),r.style.borderColor="hsl(var(--danger))",r.style.color="hsl(var(--danger))",r.setAttribute("title","Copy failed"),r.setAttribute("aria-label","Copy failed"),setTimeout(()=>{r.style.borderColor="hsl(var(--border-glass))",r.style.color="hsl(var(--text-primary))",r.setAttribute("title","Copy code"),r.setAttribute("aria-label","Copy code")},2e3)})}function Bc(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}var pr=M(()=>{});function Ro(e){return`
        <svg class="bookmark-star-icon" width="16" height="16" viewBox="0 0 24 24" fill="${e?"currentColor":"none"}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m19 21-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
        </svg>
    `}async function Do(){await Hc()}async function Hc(){try{let e=await fetch("/api/bookmarks");if(!e.ok)return;let t=await e.json();Re.clear(),t.bookmarks.forEach(n=>{Re.add(n.conversation_id)})}catch(e){console.error("Failed to load bookmarks:",e)}}async function Mc(e,t){let n=Re.has(e);try{if(n){if(!(await fetch(`/api/bookmarks/${e}`,{method:"DELETE"})).ok)throw new Error("Failed to remove bookmark");Re.delete(e),hr(t,!1)}else{if(!(await fetch("/api/bookmarks",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_id:e,notes:""})})).ok)throw new Error("Failed to add bookmark");Re.add(e),hr(t,!0)}}catch(r){console.error("Failed to toggle bookmark:",r),alert("Failed to toggle bookmark. Please try again.")}}function Rc(e){return Re.has(e)}function mr(e){let t=document.createElement("button");t.className="bookmark-star",t.dataset.conversationId=e,t.type="button";let n=Rc(e);return hr(t,n),t.addEventListener("click",r=>{r.stopPropagation(),Mc(e,t)}),t}function hr(e,t){t?(e.innerHTML=Ro(!0),e.classList.add("active"),e.title="Remove from bookmarks",e.setAttribute("aria-label","Remove from bookmarks")):(e.innerHTML=Ro(!1),e.classList.remove("active"),e.title="Add to bookmarks",e.setAttribute("aria-label","Add to bookmarks"))}async function gr(){let e=document.getElementById("results"),t=document.getElementById("conversationHeader"),n=document.getElementById("heroTitle"),r=document.getElementById("heroSubtitle"),s=document.getElementById("filters"),o=document.getElementById("chatPanel");t&&(t.style.display="none"),n&&(n.style.display="none"),r&&(r.style.display="none"),s&&(s.style.display="none"),o&&(o.style.display="none"),e.innerHTML='<div class="loading">Loading bookmarks...</div>';try{let i=await fetch("/api/bookmarks");if(!i.ok)throw new Error("Failed to load bookmarks");let a=await i.json();e.innerHTML="";let l=document.createElement("div");if(l.style.cssText=`
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid hsl(var(--border-glass));
        `,l.innerHTML=`
            <h1 style="margin: 0 0 8px 0; color: hsl(var(--text-primary));">
                Bookmarked Conversations
            </h1>
            <p style="margin: 0; color: hsl(var(--text-secondary)); font-size: 14px;">
                ${a.total} bookmark${a.total!==1?"s":""}
            </p>
        `,e.appendChild(l),a.total===0){let c=document.createElement("div");c.className="empty-state",c.innerHTML=`
                <div class="empty-icon">\u2606</div>
                <div style="font-size: 16px; margin-bottom: 8px;">No bookmarks yet</div>
                <div style="font-size: 13px;">Star conversations to save them here for quick access</div>
            `,e.appendChild(c);return}a.bookmarks.forEach(c=>{let u=document.createElement("div");u.className="result",u.style.cursor="pointer";let d=new Date(c.added_at).toLocaleString();u.innerHTML=`
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <div class="result-title">${c.title||"Untitled"}</div>
                        <div class="result-meta">
                            <span>Project: ${c.project_id||"Unknown"}</span> \u2022
                            <span>Messages: ${c.message_count||0}</span> \u2022
                            <span>Bookmarked: ${d}</span>
                        </div>
                    </div>
                    <button class="remove-bookmark-btn glass-btn" style="border-color: hsl(var(--danger)); color: hsl(var(--danger)); font-size: 12px;">
                        Remove
                    </button>
                </div>
            `,u.addEventListener("click",h=>{h.target.classList.contains("remove-bookmark-btn")||(window.location.href=`/conversation/${c.conversation_id}`)}),u.querySelector(".remove-bookmark-btn").addEventListener("click",async h=>{if(h.stopPropagation(),!!confirm(`Remove "${c.title}" from bookmarks?`))try{if(!(await fetch(`/api/bookmarks/${c.conversation_id}`,{method:"DELETE"})).ok)throw new Error("Failed to remove bookmark");Re.delete(c.conversation_id),u.remove();let g=l.querySelector("p"),m=a.total-1;g.textContent=`${m} bookmark${m!==1?"s":""}`,e.querySelectorAll(".result").length===0&&gr()}catch(p){console.error("Failed to remove bookmark:",p),alert("Failed to remove bookmark. Please try again.")}}),e.appendChild(u)})}catch(i){e.innerHTML=`<div style="color: hsl(var(--danger));">Error: ${i.message}</div>`}}var Re,vr=M(()=>{Re=new Set});function De(){let e=localStorage.getItem(yr);return e?String(e):""}function pt(){return!!De()}function Oo(e){let t=e?String(e):"";if(!t){localStorage.removeItem(yr);return}localStorage.setItem(yr,t)}function te(e){let t=De();return t&&e.set("snapshot",t),e}function Dc(e){let t=document.getElementById("datasetBanner");if(!t)return;if(!e){t.style.display="none",t.innerHTML="";return}t.style.display="block",t.innerHTML=`
        <div class="dataset-banner-title">Viewing snapshot: <strong>${Oc(e)}</strong> (read-only)</div>
        <button id="datasetReturnActive" type="button" class="secondary">Return to active</button>
    `;let n=document.getElementById("datasetReturnActive");n&&n.addEventListener("click",function(){Oo(""),window.location.href="/"})}function Oc(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}function Pc(e){let t=["indexMissingButton","createBackupButton","manageBackupsButton","analyticsButton","dashboardsButton","chatSend","chatStop","semanticHighlights","saveQueryButtonInline"];for(let r of t){let s=document.getElementById(r);s&&(s.disabled=!0,s.title=`Disabled in snapshot mode (${e})`)}let n=document.getElementById("chatPanel");n&&(n.style.display="none")}async function jc(e){let t=await fetch("/api/backup/list");if(!t.ok)return[];let n=await t.json();return(Array.isArray(n.backups)?n.backups:[]).filter(function(s){return Object.prototype.hasOwnProperty.call(s,"snapshot_browsable")?!!s.snapshot_browsable:!0}).map(function(s){return String(s.backup_path||"").split(/[/\\]/).pop()}).filter(Boolean)}async function Po(){let e=document.getElementById("datasetSelect");if(!e)return;try{let r=await fetch("/api/status/features");if(r.ok){let s=await r.json();if(!!!(s&&s.snapshots&&s.snapshots.enabled)){let i=document.getElementById("datasetPanel");i&&(i.style.display="none");return}}}catch{}let t=De();e.innerHTML="";let n=document.createElement("option");n.value="",n.textContent="Active index",e.appendChild(n);try{let r=await jc(e);for(let s of r){let o=document.createElement("option");o.value=s,o.textContent=s,e.appendChild(o)}}catch{}e.value=t,Dc(t),t&&Pc(t),e.addEventListener("change",function(){Oo(e.value),window.location.href="/"})}var yr,Ke=M(()=>{yr="searchatSnapshotName"});function qc(e){return e==="opencode"?"OpenCode":e==="vibe"?"Vibe":e==="codex"?"Codex":e==="gemini"?"Gemini CLI":e==="continue"?"Continue":e==="cursor"?"Cursor":e==="aider"?"Aider":e==="omp"?"Oh My Pi":"Claude Code"}async function jo(e,t){t.innerHTML='<div class="loading">Finding similar conversations...</div>';try{let n=te(new URLSearchParams({limit:"5"})),r=await fetch(`/api/conversation/${e}/similar?${n.toString()}`);if(!r.ok){let i=await r.json().catch(()=>null),a=i&&i.detail?i.detail:"Failed to load similar conversations";t.innerHTML=`<div style="color: hsl(var(--text-tertiary)); padding: 20px; text-align: center;">${a}</div>`;return}let s=await r.json();if(!s.similar_conversations||s.similar_conversations.length===0){t.innerHTML=`
                <div style="
                    text-align: center;
                    padding: 40px 20px;
                    color: hsl(var(--text-tertiary));
                ">
                    <div style="font-size: 48px; margin-bottom: 16px;">\u{1F50D}</div>
                    <div style="font-size: 16px; margin-bottom: 8px;">No similar conversations found</div>
                    <div style="font-size: 13px;">This conversation appears to be unique</div>
                </div>
            `;return}let o=`
            <div style="
                margin-bottom: 20px;
                padding: 12px 16px;
                background: hsl(var(--bg-surface));
                border-radius: 8px;
                border: 1px solid hsl(var(--border-glass));
            ">
                <div style="font-size: 16px; font-weight: 500; color: hsl(var(--text-primary)); margin-bottom: 4px;">
                    \u{1F517} ${s.similar_count} Related Conversation${s.similar_count!==1?"s":""}
                </div>
                <div style="font-size: 13px; color: hsl(var(--text-tertiary));">
                    Found using semantic similarity analysis
                </div>
            </div>
        `;s.similar_conversations.forEach((i,a)=>{let l=qc(i.tool),c=Math.round(i.similarity_score*100),u=new Date(i.created_at).toLocaleDateString(),d="hsl(var(--success))";c<70&&(d="hsl(var(--warning))"),c<50&&(d="hsl(var(--text-tertiary))"),o+=`
                <div class="similar-conversation-item" data-conversation-id="${i.conversation_id}" style="
                    background: hsl(var(--bg-elevated));
                    border: 1px solid hsl(var(--border-glass));
                    border-radius: 8px;
                    padding: 14px 16px;
                    margin-bottom: 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                " onmouseover="this.style.borderColor='hsl(var(--accent))'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='hsl(var(--border-glass))'; this.style.transform='translateY(0)'">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                        <div style="flex: 1;">
                            <div style="font-size: 15px; font-weight: 500; color: hsl(var(--text-primary)); margin-bottom: 4px;">
                                ${i.title}
                            </div>
                            <div style="font-size: 12px; color: hsl(var(--text-tertiary));">
                                <span class="tool-badge ${i.tool}" style="font-size: 11px; padding: 2px 6px;">${l}</span>
                                <span style="margin-left: 8px;">${i.project_id}</span>
                                <span style="margin-left: 8px;">\u2022</span>
                                <span style="margin-left: 8px;">${i.message_count} messages</span>
                                <span style="margin-left: 8px;">\u2022</span>
                                <span style="margin-left: 8px;">${u}</span>
                            </div>
                        </div>
                        <div style="
                            background: ${d};
                            color: white;
                            padding: 4px 10px;
                            border-radius: 4px;
                            font-size: 12px;
                            font-weight: 600;
                            white-space: nowrap;
                            margin-left: 12px;
                        ">
                            ${c}% match
                        </div>
                    </div>
                </div>
            `}),t.innerHTML=o,t.querySelectorAll(".similar-conversation-item").forEach(i=>{i.addEventListener("click",()=>{let a=i.dataset.conversationId;window.location.href=`/conversation/${a}`})})}catch(n){t.innerHTML=`<div style="color: hsl(var(--danger));">Error: ${n.message}</div>`}}var qo=M(()=>{Ke()});var Fo={};Fr(Fo,{addCheckboxToResult:()=>zt,initBulkExport:()=>Nc,isBulkModeActive:()=>Kc,toggleBulkMode:()=>Fc});function Nc(){}function Fc(){Xe=!Xe,pe.clear();let t=document.getElementById("results").querySelectorAll(".result");Xe?(t.forEach(n=>{let r=No(n.dataset.conversationId);n.insertBefore(r,n.firstChild)}),Vc()):(t.forEach(n=>{let r=n.querySelector(".bulk-checkbox");r&&r.remove()}),Uc()),Jc()}function No(e){let t=document.createElement("div");t.className="bulk-checkbox",t.style.cssText=`
        float: left;
        margin-right: 12px;
        margin-top: 2px;
    `;let n=document.createElement("input");return n.type="checkbox",n.dataset.conversationId=e,n.style.cssText=`
        width: 18px;
        height: 18px;
        cursor: pointer;
        accent-color: hsl(var(--accent));
    `,n.addEventListener("change",r=>{r.stopPropagation(),n.checked?pe.add(e):pe.delete(e),xr()}),t.appendChild(n),t}function Vc(){let e=document.getElementById("bulkToolbar");e||(e=document.createElement("div"),e.id="bulkToolbar",e.className="glass-elevated",e.style.cssText=`
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 16px;
        `,e.innerHTML=`
            <span id="bulkCount" style="font-size: 14px; color: hsl(var(--text-primary)); font-weight: 500;">
                0 selected
            </span>
            <button id="bulkSelectAll" class="glass-btn">Select All</button>
            <button id="bulkDeselectAll" class="glass-btn">Deselect All</button>
            <div style="width: 1px; height: 24px; background: hsl(var(--border-glass));"></div>
            <button id="bulkExportJson" class="glass-btn glass-btn-primary">Export JSON</button>
            <button id="bulkExportMarkdown" class="glass-btn glass-btn-primary">Export Markdown</button>
            <button id="bulkExportText" class="glass-btn glass-btn-primary">Export Text</button>
        `,document.body.appendChild(e),document.getElementById("bulkSelectAll").addEventListener("click",zc),document.getElementById("bulkDeselectAll").addEventListener("click",Wc),document.getElementById("bulkExportJson").addEventListener("click",()=>br("json")),document.getElementById("bulkExportMarkdown").addEventListener("click",()=>br("markdown")),document.getElementById("bulkExportText").addEventListener("click",()=>br("text"))),e.style.display="flex"}function Uc(){let e=document.getElementById("bulkToolbar");e&&(e.style.display="none")}function xr(){let e=document.getElementById("bulkCount");if(e){let t=pe.size;e.textContent=`${t} selected`}}function zc(){document.getElementById("results").querySelectorAll('.bulk-checkbox input[type="checkbox"]').forEach(n=>{n.checked=!0,pe.add(n.dataset.conversationId)}),xr()}function Wc(){document.getElementById("results").querySelectorAll('.bulk-checkbox input[type="checkbox"]').forEach(n=>{n.checked=!1}),pe.clear(),xr()}async function br(e){if(pe.size===0){alert("Please select at least one conversation to export");return}if(pe.size>100){alert("Maximum 100 conversations can be exported at once");return}try{let t=te(new URLSearchParams),n=t.toString()?`/api/conversations/bulk-export?${t.toString()}`:"/api/conversations/bulk-export",r=await fetch(n,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_ids:Array.from(pe),format:e})});if(!r.ok)throw new Error("Export failed");let s=await r.blob(),o=window.URL.createObjectURL(s),i=document.createElement("a");i.href=o,i.download=`searchat_export_${Date.now()}.zip`,document.body.appendChild(i),i.click(),window.URL.revokeObjectURL(o),i.remove();let a=document.getElementById("bulkCount");if(a){let l=a.textContent;a.textContent="\u2713 Export complete!",a.style.color="hsl(var(--success))",setTimeout(()=>{a.textContent=l,a.style.color="hsl(var(--text-primary))"},3e3)}}catch(t){console.error("Bulk export failed:",t),alert("Failed to export conversations. Please try again.")}}function Jc(){let e=document.getElementById("bulkModeToggle");e&&(Xe?(e.textContent="\u2715 Exit Bulk Mode",e.style.borderColor="hsl(var(--danger))",e.style.color="hsl(var(--danger))"):(e.textContent="Bulk Export",e.style.borderColor="hsl(var(--accent))",e.style.color=""))}function Kc(){return Xe}function zt(e,t){if(Xe){let n=No(t);e.insertBefore(n,e.firstChild)}}var pe,Xe,Er=M(()=>{Ke();pe=new Set,Xe=!1});function Sr(e){ht=e}function Wt(){return(Q-1)*wr}function _r(e,t){if(ht===0)return;let n=Math.ceil(ht/wr);if(n<=1)return;let r=`
        <div class="pagination glass" style="display: flex; justify-content: center; align-items: center; gap: 12px; margin: 32px 0; padding: 20px;">
            <button
                onclick="window.goToPage(1)"
                ${Q===1?"disabled":""}
                class="glass-btn"
                title="First page"
            >
                \xAB First
            </button>

            <button
                onclick="window.goToPage(${Q-1})"
                ${Q===1?"disabled":""}
                class="glass-btn"
                title="Previous page"
            >
                \u2039 Previous
            </button>

            <div style="display: flex; gap: 6px; align-items: center;">
                ${Xc(n)}
            </div>

            <button
                onclick="window.goToPage(${Q+1})"
                ${Q===n?"disabled":""}
                class="glass-btn"
                title="Next page"
            >
                Next \u203A
            </button>

            <button
                onclick="window.goToPage(${n})"
                ${Q===n?"disabled":""}
                class="glass-btn"
                title="Last page"
            >
                Last \xBB
            </button>

            <div style="margin-left: 16px; color: hsl(var(--text-tertiary)); font-size: 14px;">
                Page ${Q} of ${n} (${ht} results)
            </div>
        </div>
    `;e.insertAdjacentHTML("beforeend",r)}function Xc(e){let n=[];if(e<=7)for(let r=1;r<=e;r++)n.push(r);else if(Q<=4){for(let r=1;r<=5;r++)n.push(r);n.push("..."),n.push(e)}else if(Q>=e-3){n.push(1),n.push("...");for(let r=e-4;r<=e;r++)n.push(r)}else{n.push(1),n.push("...");for(let r=Q-1;r<=Q+1;r++)n.push(r);n.push("..."),n.push(e)}return n.map(r=>r==="..."?'<span style="color: hsl(var(--text-tertiary)); padding: 8px;">...</span>':`
            <button
                onclick="window.goToPage(${r})"
                class="${r===Q?"glass-btn glass-btn-primary":"glass-btn"}"
                style="min-width: 36px;"
            >
                ${r}
            </button>
        `).join("")}async function Jt(e,t){let n=Math.ceil(ht/wr);e<1||e>n||(Q=e,window.scrollTo({top:0,behavior:"smooth"}),t&&await t())}function Vo(){Q=1}var Q,ht,wr,Cr=M(()=>{Q=1,ht=0,wr=20});function Qc(e){return new Promise(function(t){setTimeout(t,e)})}function Wo(){return Kt}function zo(e){let t=document.getElementById("projectSummary");if(!t)return;if(!e){t.style.display="none",t.innerHTML="";return}let n=null;for(let r of Kt)if(r.project_id===e){n=r;break}if(!n){t.style.display="none",t.innerHTML="";return}t.style.display="block",t.innerHTML=`
        <div class="project-summary-title">Project Summary</div>
        <div class="project-summary-details">
            <span><strong>${n.conversation_count}</strong> conversations</span>
            <span><strong>${n.message_count}</strong> messages</span>
            <span>Updated ${new Date(n.updated_at).toLocaleDateString()}</span>
        </div>
    `}async function Xt(){let e=te(new URLSearchParams),t=e.toString()?`/api/projects/summary?${e.toString()}`:"/api/projects/summary",n=await fetch(t);if(n.status===503){let i=await n.json();if(i&&i.status==="warming")return await Qc(i.retry_after_ms||500),Xt();console.error("Failed to load projects:",i);return}if(!n.ok){let i=await n.json().catch(function(){return null});console.error("Failed to load projects:",i);return}let r=await n.json(),s=document.getElementById("project"),o=s.value;Kt=Array.isArray(r)?r:[];for(let i of Kt){let a=document.createElement("option");a.value=i.project_id;let l=`${i.project_id} (${i.conversation_count})`;i.project_id.startsWith("opencode-")?a.textContent=`OpenCode \u2022 ${l}`:i.project_id.startsWith("vibe-")?a.textContent=`Vibe \u2022 ${l}`:a.textContent=`Claude Code \u2022 ${l}`,s.appendChild(a)}if(o&&(s.value=o),!Uo){let i=function(){zo(s.value)};s.addEventListener("change",i),Uo=!0}zo(s.value)}async function Jo(){let e=document.getElementById("results");e.innerHTML='<div class="loading">Scanning for missing conversations... This may take a minute...</div>';try{let n=await(await fetch("/api/index_missing",{method:"POST"})).json();if(n.success){let r=n.failed_conversations||0,s=n.empty_conversations||0,o=[];s>0&&o.push(`<strong>${s} empty sessions</strong> skipped`),r>0&&o.push(`<strong style="color: hsl(var(--danger));">${r} failed</strong>`);let i=o.length>0?" | "+o.join(" | "):"";if(n.new_conversations===0){let a=r>0?"notification-warning":"notification-info",l=r>0?`All valid conversations indexed (${r} corrupt files skipped)`:"All conversations are already indexed";e.innerHTML=`
                    <div class="notification ${a}">
                        <strong>${l}</strong>
                        <div class="notification-details">
                            <strong>Total files:</strong> ${n.total_files} | <strong>Already indexed:</strong> ${n.already_indexed}${i}
                        </div>
                        <div class="notification-hint">
                            The live file watcher will automatically index new conversations as you create them.
                        </div>
                    </div>
                `}else{let a=r>0?"notification-warning":"notification-success";e.innerHTML=`
                    <div class="notification ${a}">
                        <strong>Added ${n.new_conversations} conversations to index</strong>
                        <div class="notification-details">
                            <strong>Total files:</strong> ${n.total_files} | <strong>Previously indexed:</strong> ${n.already_indexed} | <strong>Time:</strong> ${n.time_seconds}s${i}
                        </div>
                        <div class="notification-hint">
                            Your new conversations are now searchable!
                        </div>
                    </div>
                `;let l=document.getElementById("project");l.innerHTML='<option value="">All Projects</option>',await Xt()}}else e.innerHTML='<div class="notification notification-error"><strong>Indexing failed</strong></div>'}catch(t){e.innerHTML=`<div style="color: hsl(var(--danger));">Error: ${t.message}</div>`}}async function Ko(e=!1){if(!e&&!(window.glassConfirm?await window.glassConfirm("Stop the search server? You will need to restart it from the terminal."):confirm("Stop the search server? You will need to restart it from the terminal.")))return;let t=document.getElementById("results");t.innerHTML='<div class="loading">Checking server status...</div>';try{let s=await(await fetch(e?"/api/shutdown?force=true":"/api/shutdown",{method:"POST"})).json();if(s.success){let o="background: hsl(var(--danger));",i="";s.forced&&(o="background: hsl(var(--warning)); border-left-color: hsl(var(--danger));",i='<div style="margin-top: 8px; color: #fff; font-weight: 600;">\u26A0 FORCED SHUTDOWN - Indexing was interrupted. Index may be inconsistent.</div>'),t.innerHTML=`
                <div class="results-header" style="${o} padding: 15px;">
                    <strong>\u2713 Server shutting down</strong>
                    ${i}
                    <div style="margin-top: 8px; opacity: 0.9;">
                        You can close this window. To restart, run: <code style="background: #333; padding: 2px 6px;">searchat-web</code>
                    </div>
                </div>
            `}else s.indexing_in_progress?t.innerHTML=`
                <div class="results-header" style="background: hsl(var(--warning)); padding: 15px; border-left: 3px solid hsl(var(--danger));">
                    <strong>\u26A0 Indexing in Progress</strong>
                    <div style="margin-top: 8px;">
                        <strong>Operation:</strong> ${s.operation}<br>
                        <strong>Files:</strong> ${s.files_total}<br>
                        <strong>Elapsed:</strong> ${s.elapsed_seconds}s
                    </div>
                    <div style="margin-top: 12px; color: #fff;">
                        Shutting down during indexing may corrupt data.
                    </div>
                    <div style="margin-top: 12px;">
                        <button onclick="import('./modules/api.js').then(m => m.shutdownServer(true))" style="background: hsl(var(--danger)); color: white; border: none; padding: 8px 16px; cursor: pointer; margin-right: 10px;">
                            Force Stop (Unsafe)
                        </button>
                        <button onclick="document.getElementById('results').innerHTML = ''" style="background: hsl(var(--success)); color: white; border: none; padding: 8px 16px; cursor: pointer;">
                            Wait for Completion
                        </button>
                    </div>
                </div>
            `:t.innerHTML='<div style="color: hsl(var(--danger));">Shutdown failed</div>'}catch{t.innerHTML=`
            <div class="results-header" style="background: hsl(var(--danger)); padding: 15px;">
                <strong>\u2713 Server stopped</strong>
                <div style="margin-top: 8px; opacity: 0.9;">
                    You can close this window. To restart, run: <code style="background: #333; padding: 2px 6px;">searchat-web</code>
                </div>
            </div>
        `}}var Kt,Uo,kr=M(()=>{Ke();Kt=[],Uo=!1});function Gt(e){return Gc.every(t=>e?.components?.[t]==="ready")}function nd(e){if(!e)return!1;try{return localStorage.getItem(Qo)===String(e)}catch(t){return console.warn("Splash: failed to read localStorage",t),!1}}function Yo(e){if(e)try{localStorage.setItem(Qo,String(e))}catch(t){console.warn("Splash: failed to write localStorage",t)}}function rd(){try{localStorage.removeItem(Yc)}catch(e){console.warn("Splash: failed to clear legacy localStorage key",e)}}function Go(){let e=document.getElementById("sidebarWarmupIndicator");return e?getComputedStyle(e).display!=="none"?(mt===null&&(mt=Date.now()),Date.now()-mt>ed?(console.warn("isWarmingUp: warmup exceeded maximum duration, unblocking search/chat"),e.style.display="none",mt=null,!1):!0):(mt=null,!1):!1}function Yt(e){if(e===Xo)return;Xo=e;let t=document.getElementById("search"),n=document.querySelector(".search-wrap"),r=document.getElementById("chatNavLink");if(t&&(t.disabled=e),n&&n.classList.toggle("warming-up",e),r)if(e)r.dataset.href=r.getAttribute("href"),r.removeAttribute("href"),r.setAttribute("aria-disabled","true"),r.style.pointerEvents="none",r.style.opacity="0.5";else{let s=r.dataset.href;s&&(r.setAttribute("href",s),delete r.dataset.href),r.removeAttribute("aria-disabled"),r.style.pointerEvents="",r.style.opacity=""}}async function Zo(){try{rd();let t=await(await fetch("/api/status")).json();if(Qt=t.server_started_at||t.warmup_started_at||null,Gt(t)){Yo(Qt),Yt(!1);return}if(nd(Qt))return;Yt(!0),sd(t),ad()}catch(e){console.error("Failed to check warmup status:",e)}}function sd(e){let t=document.createElement("div");t.id="splashOverlay",t.className="splash-overlay";let n=document.createElement("div");n.className="splash-content";let r=document.createElement("div");r.className="splash-header",r.innerHTML=`
        <h1><span class="text-shimmer">searchat</span></h1>
        <p>Warming up search engine...</p>
    `,n.appendChild(r);let s=document.createElement("div");s.className="splash-highlights",Zc.forEach(l=>{let c=document.createElement("div");c.className="splash-highlight-item stat-card",c.innerHTML=`
            <span class="splash-highlight-icon">${l.icon}</span>
            <div class="splash-highlight-text">
                <div class="splash-highlight-title">${l.title}</div>
                <div class="splash-highlight-desc">${l.desc}</div>
            </div>
        `,s.appendChild(c)}),n.appendChild(s);let o=document.createElement("div");o.id="splashProgress",o.className="splash-progress-container",n.appendChild(o);let i=document.createElement("div");i.className="splash-actions",i.innerHTML=`
        <a href="/docs/infographics.html" target="_blank" class="splash-btn splash-btn-secondary">
            View Full Infographics
        </a>
        <button id="splashDismiss" class="splash-btn splash-btn-primary">
            Get Started
        </button>
    `,n.appendChild(i),t.appendChild(n),document.body.appendChild(t);let a=document.getElementById("splashDismiss");a&&(a.onclick=ld),ei(e),setTimeout(()=>t.classList.add("splash-visible"),10)}function ei(e){let t=document.getElementById("splashProgress");if(!t)return;t.innerHTML="",["services","duckdb","parquet","search_engine","embedder","embedded_model","faiss","metadata","indexer"].forEach(r=>{let s=e.components[r];if(!s)return;let o=od(r,s,e.errors[r]);t.appendChild(o)})}function od(e,t,n){let r=document.createElement("div");r.className="splash-progress-item";let s="";t==="ready"?s="\u2713":t==="error"?s="\u2717":s="\u23F3";let o=0,i="";t==="ready"?(o=100,i="Ready"):t==="loading"?(o=60,i=n||"Loading..."):t==="error"?(o=0,i=n||"Error"):(o=0,e==="embedded_model"?i=n||"Not enabled":i=n||"Idle");let l=t==="loading"?'<div class="splash-spinner" aria-hidden="true"></div>':"";return r.innerHTML=`
        <span class="splash-progress-icon">${s}</span>
        <span class="splash-progress-name">${id(e)}</span>
        ${l}
        <div class="splash-progress-bar">
            <div class="splash-progress-fill" style="width: ${o}%"></div>
        </div>
        <span class="splash-progress-status">${i}</span>
    `,r.classList.add(`splash-progress-${t}`),r}function id(e){return{services:"Services",duckdb:"Database",parquet:"Data Files",search_engine:"Search Engine",faiss:"FAISS Index",metadata:"Metadata",embedder:"AI Embeddings",embedded_model:"Embedded LLM",indexer:"Indexer"}[e]||e}function ad(){he&&clearInterval(he),he=setInterval(async()=>{try{let t=await(await fetch("/api/status")).json();ei(t),Gt(t)&&he&&(clearInterval(he),he=null)}catch(e){console.error("Failed to poll status:",e)}},500)}async function ld(){Yo(Qt);let e=!1;try{let n=await fetch("/api/status");if(!n.ok)throw new Error(`Status API returned ${n.status}`);let r=await n.json();e=Gt(r)}catch(n){console.warn("dismissSplash: status check failed, assuming not ready",n)}he&&(clearInterval(he),he=null);let t=document.getElementById("splashOverlay");t&&(t.classList.remove("splash-visible"),setTimeout(()=>t.remove(),300)),e?Yt(!1):cd()}function cd(){if(Qe)return;let e=document.getElementById("sidebarWarmupIndicator");if(!e){console.warn("showSidebarWarmupIndicator: #sidebarWarmupIndicator not found in DOM");return}e.style.display="";let t=0;Qe=setInterval(async()=>{try{let n=await fetch("/api/status");if(!n.ok)throw new Error(`HTTP ${n.status}`);let r=await n.json(),s=Gt(r);t=0,s&&(clearInterval(Qe),Qe=null,e.style.display="none",Yt(!1))}catch(n){if(t++,console.warn("Sidebar warmup poll failed:",n),t>=td){clearInterval(Qe),Qe=null;let r=e.querySelector(".sidebar-warmup-label");r&&(r.textContent="Warmup check failed \u2014 reload page")}}},500)}var Qo,Yc,Gc,Zc,he,Qt,Qe,mt,Xo,ed,td,Ir=M(()=>{Qo="searchatSplashDismissedServerStartedAt",Yc="searchatSplashShown",Gc=["embedder","faiss","metadata"],Zc=[{icon:"\u{1F50D}",title:"3 Search Modes",desc:"Hybrid (DuckDB FTS + FAISS), Semantic, Keyword"},{icon:"\u26A1",title:"<100ms Search",desc:"Ultra-fast hybrid search with RRF fusion"},{icon:"\u{1F3AF}",title:"Smart Matching",desc:"Autocomplete, synonym expansion, cross-encoder re-ranking"},{icon:"\u{1F916}",title:"8 AI Agents",desc:"Claude, Vibe, OpenCode, Codex, Gemini, Continue, Cursor, Aider"},{icon:"\u{1F50C}",title:"MCP Server",desc:"8 tools for MCP clients (search, patterns, agent config)"},{icon:"\u{1F4AC}",title:"Session Chat",desc:"Multi-turn RAG with 30-min session persistence"},{icon:"\u{1F9E9}",title:"Pattern Mining",desc:"Extract recurring coding patterns via LLM"},{icon:"\u{1F4CB}",title:"Agent Config",desc:"Generate CLAUDE.md, copilot-instructions, cursorrules"},{icon:"\u{1F517}",title:"Similarity Search",desc:"Discover related conversations"},{icon:"\u{1F516}",title:"Bookmarks",desc:"Save and annotate favorites"},{icon:"\u{1F4CA}",title:"Analytics",desc:"Track search patterns and trends"},{icon:"\u{1F6E1}\uFE0F",title:"Append-Only",desc:"Never deletes existing data"},{icon:"\u{1F4C8}",title:"55+ API Endpoints",desc:"Comprehensive REST API with 14 routers"}],he=null,Qt=null,Qe=null,mt=null,Xo=!1,ed=12e4,td=20});var rn={};Fr(rn,{initProjectSuggestion:()=>Lr,loadConversationView:()=>Ee,resumeSession:()=>Ye,search:()=>xe,showAllConversations:()=>gt,showSearchView:()=>Y,toggleCustomDate:()=>nn});function si(){return`
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" stroke-width="2"></rect>
            <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" stroke="currentColor" stroke-width="2"></path>
        </svg>
    `}function dd(){return`
        <svg class="copy-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
    `}function ud(e){let t=Wo();if(!Array.isArray(t)||t.length===0)return null;let n=e.trim().toLowerCase();if(n.length<3)return null;let r=fd(n);if(r.length===0)return null;let s=null,o=0;for(let i of t){let a=String(i.project_id||"").toLowerCase();if(a){if(n.includes(a)){a.length>o&&(o=a.length,s=i);continue}for(let l of r)a.includes(l)&&l.length>o&&(o=l.length,s=i)}}return s}function fd(e){let t=[],n=e.split(/[^a-z0-9_-]+/);for(let r of n)r.length>=3&&t.push(r);return t}function Lr(){let e=document.getElementById("search"),t=document.getElementById("projectSuggestion"),n=document.getElementById("project");if(!e||!t||!n)return;function r(){t.style.display="none",t.innerHTML=""}function s(){let l=ud(e.value);if(!l){r();return}if(n.value===l.project_id){r();return}t.style.display="flex",t.innerHTML=`
            <span>Search within <strong>${oe(l.project_id)}</strong>?</span>
            <button type="button" data-project-id="${oe(l.project_id)}">Scope to project</button>
        `}function o(){s()}function i(){s()}function a(l){let c=l.target.closest("button");if(!c)return;let u=c.dataset.projectId;u&&(n.value=u,r(),window.search&&window.search())}e.addEventListener("input",o),n.addEventListener("change",i),t.addEventListener("click",a),s()}function oe(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}function Br(e){return e==="opencode"?"OpenCode":e==="vibe"?"Vibe":e==="codex"?"Codex":e==="gemini"?"Gemini CLI":e==="continue"?"Continue":e==="cursor"?"Cursor":e==="aider"?"Aider":e==="omp"?"Oh My Pi":"Claude Code"}function pd(e){let t=String(e||"").toLowerCase().replace(/\\/g,"/");return t.includes("/.local/share/opencode/")?"opencode":t.includes("/.codex/")?"codex":t.includes("/.continue/sessions/")&&t.endsWith(".json")?"continue":t.includes(".vscdb.cursor/")&&t.endsWith(".json")?"cursor":t.includes("/.gemini/tmp/")&&t.includes("/chats/")&&t.endsWith(".json")?"gemini":t.endsWith("/.aider.chat.history.md")||t.endsWith(".aider.chat.history.md")?"aider":t.includes("/.omp/agent/sessions/")?"omp":t.includes("/.claude/")&&t.endsWith(".jsonl")?"claude":t.includes("/.vibe/")&&t.endsWith(".json")?"vibe":t.endsWith(".jsonl")?"claude":"vibe"}function ni(e){return e.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}function ri(e,t){return e&&e.detail?e.detail:e&&e.errors?JSON.stringify(e.errors):t}function hd(e){if(!Array.isArray(e))return[];let t=[];for(let n of e){if(typeof n!="string")continue;let r=n.trim();r.length>1&&t.push(r)}return t}function Zt(e,t,n){if(!e)return"";let r=oe(e),s=(t||"").trim();if(s.length>=2&&s!=="*"){let i=new RegExp(`(${ni(s)})`,"gi");r=r.replace(i,'<mark class="mark-exact">$1</mark>')}let o=hd(n);for(let i of o){if(!i||i.toLowerCase()===s.toLowerCase())continue;let a=new RegExp(`(${ni(i)})`,"gi");r=r.replace(a,'<mark class="mark-semantic">$1</mark>')}return r}function md(e,t){let n=`snippet-code-${$r++}`;tn.set(n,e);let r=oe(e),s=e.split(`
`).length,o=s>30;return{html:`
            <div class="snippet-code-block" data-code-id="${n}" data-collapsed="${o}">
                <div class="snippet-code-header">
                    <span class="snippet-code-lang">${oe(t||"plaintext")}</span>
                    <span class="snippet-code-lines">${s} lines</span>
                    <div class="snippet-code-actions">
                        <button class="snippet-copy" type="button" data-code-id="${n}" title="Copy snippet" aria-label="Copy snippet">${si()}</button>
                        ${o?'<button class="snippet-toggle">Expand</button>':""}
                    </div>
                </div>
                <pre class="snippet-code ${o?"collapsed":""}"><code>${r}</code></pre>
            </div>
        `,collapsed:o}}function oi(e,t,n){if(!e)return"";let r=/```(\w+)?\n([\s\S]*?)```/g,s=0,o,i="";for(;(o=r.exec(e))!==null;){let l=e.slice(s,o.index);l&&(i+=`<div class="snippet-text">${Zt(l,t,n)}</div>`);let c=o[1]||"plaintext",u=o[2]||"",d=md(u.trim(),c);i+=d.html,s=o.index+o[0].length}let a=e.slice(s);return a&&(i+=`<div class="snippet-text">${Zt(a,t,n)}</div>`),i||(i=`<div class="snippet-text">${Zt(e,t,n)}</div>`),i}function gd(e){let t=e.summary||{added:0,removed:0,unchanged:0},n=e.added||[],r=e.removed||[],s=e.unchanged||[];return`
        <div class="diff-summary">
            <span class="diff-count added">+${t.added}</span>
            <span class="diff-count removed">-${t.removed}</span>
            <span class="diff-count unchanged">${t.unchanged} unchanged</span>
        </div>
        <div class="diff-section">
            <div class="diff-title">Added</div>
            <pre class="diff-block diff-added">${oe(n.join(`
`))}</pre>
        </div>
        <div class="diff-section">
            <div class="diff-title">Removed</div>
            <pre class="diff-block diff-removed">${oe(r.join(`
`))}</pre>
        </div>
        <details class="diff-section">
            <summary class="diff-title">Unchanged</summary>
            <pre class="diff-block diff-unchanged">${oe(s.join(`
`))}</pre>
        </details>
    `}function ii(e){if(ti)return;async function t(n){let r=n.target,s=r.closest(".snippet-copy");if(s){n.stopPropagation();let o=s.dataset.codeId,i=tn.get(o)||"";if(!i)return;try{await navigator.clipboard.writeText(i),s.innerHTML=dd(),s.classList.add("is-copied"),s.setAttribute("title","Copied"),s.setAttribute("aria-label","Copied"),setTimeout(function(){s.innerHTML=si(),s.classList.remove("is-copied"),s.setAttribute("title","Copy snippet"),s.setAttribute("aria-label","Copy snippet")},1500)}catch(a){console.error("Failed to copy snippet code:",a),s.classList.add("is-copy-error"),s.setAttribute("title","Copy failed"),s.setAttribute("aria-label","Copy failed"),setTimeout(function(){s.classList.remove("is-copy-error"),s.setAttribute("title","Copy snippet"),s.setAttribute("aria-label","Copy snippet")},1500)}return}if(r.classList.contains("snippet-toggle")){n.stopPropagation();let o=r.closest(".snippet-code-block");if(!o)return;let i=o.querySelector(".snippet-code");if(!i)return;let a=i.classList.contains("collapsed");i.classList.toggle("collapsed"),r.textContent=a?"Collapse":"Expand";return}if(r.classList.contains("diff-btn")){n.stopPropagation();let o=r.closest(".result");if(!o)return;let i=o.querySelector(".result-diff");if(!i||!i.classList.toggle("open")||i.dataset.loaded==="true")return;let l=o.dataset.conversationId,c=o.dataset.messageStart,u=o.dataset.messageEnd,d=new URLSearchParams;c&&d.append("source_start",c),u&&d.append("source_end",u),te(d),i.innerHTML='<div class="loading">Loading diff...</div>';try{let f=await fetch(`/api/conversation/${l}/diff?${d.toString()}`);if(!f.ok){let p=await f.json().catch(()=>null),g=p&&p.detail?p.detail:"Failed to load diff";i.innerHTML=`<div class="diff-error">${g}</div>`;return}let h=await f.json();i.innerHTML=gd(h),i.dataset.loaded="true"}catch(f){i.innerHTML=`<div class="diff-error">Error: ${f.message}</div>`}}}e.addEventListener("click",t),ti=!0}function vd(e){return new Promise(function(t){setTimeout(t,e)})}async function yd(e,t){let n=String(e||"");if(n)try{if(await navigator.clipboard.writeText(n),!t)return;let r=t.textContent;t.textContent="Copied",t.classList.add("copied"),setTimeout(function(){t.textContent=r,t.classList.remove("copied")},1500)}catch(r){console.error("Failed to copy text:",r)}}async function xe(e=!0,t=0){if(Go()){console.debug("search(): blocked by warmup guard"),document.getElementById("results").innerHTML='<div class="loading">Search engine is still warming up\u2026</div>';return}Tr+=1;let n=Tr,r=document.getElementById("search").value,s=document.getElementById("project").value,o=document.getElementById("tool").value,i=document.getElementById("date").value;if(!r&&!s&&!o&&!i){document.getElementById("results").innerHTML="<div>Enter a search query or select a filter</div>";return}e&&Vo();let a=document.getElementById("results");a.innerHTML='<div class="loading">Searching...</div>',tn.clear(),$r=0;let l=new URLSearchParams({q:r||"*",mode:document.getElementById("mode").value,project:document.getElementById("project").value,tool:o,date:document.getElementById("date").value,sort_by:document.getElementById("sortBy").value,offset:Wt()}),c=document.getElementById("chatProvider")?.value,u=document.getElementById("chatModel")?.value;if(document.getElementById("semanticHighlights")?.checked&&r.trim().length>=4&&document.getElementById("mode").value!=="keyword"&&c&&(l.append("highlight","true"),l.append("highlight_provider",c),u&&l.append("highlight_model",u)),document.getElementById("date").value==="custom"){let y=document.getElementById("dateFrom").value,x=document.getElementById("dateTo").value;y&&l.append("date_from",y),x&&l.append("date_to",x)}let h=document.getElementById("project").value;o||(h.startsWith("opencode-")?l.append("tool","opencode"):h.startsWith("vibe-")?l.append("tool","vibe"):h==="codex"?l.append("tool","codex"):h==="gemini"||h.startsWith("gemini-")?l.append("tool","gemini"):h==="continue"||h.startsWith("continue-")?l.append("tool","continue"):h==="cursor"||h.startsWith("cursor-")?l.append("tool","cursor"):(h==="aider"||h.startsWith("aider-"))&&l.append("tool","aider")),te(l);let p=await fetch(`/api/search?${l}`);if(p.status===503){let y=await p.json();if(y&&y.status==="warming"){let b=y.retry_after_ms||500,j=Math.min(b*Math.pow(2,t),5e3);if(t>=6){let V=y.errors?JSON.stringify(y.errors):"No warmup details available.";a.innerHTML=`
                    <div style="color: hsl(var(--danger)); margin-bottom: 8px;">Search warmup is taking too long.</div>
                    <div style="font-size: 12px; color: #888; margin-bottom: 10px;">${V}</div>
                    <button id="fallbackKeyword" style="background: hsl(var(--accent)); padding: 6px 10px; border: none; border-radius: 6px; color: white; cursor: pointer;">Switch to Keyword Mode</button>
                `;let B=document.getElementById("fallbackKeyword");B&&B.addEventListener("click",function(){return document.getElementById("mode").value="keyword",xe()});return}return a.innerHTML='<div class="loading">Warming up search engine\u2026</div>',await vd(j),n===Tr?xe(!1,t+1):void 0}let x=ri(y,"Search warming failed");a.innerHTML=`<div style="color: hsl(var(--danger));">${x}</div>`;return}if(!p.ok){let y=await p.json().catch(()=>null),x=ri(y,"Search failed");a.innerHTML=`<div style="color: hsl(var(--danger));">${x}</div>`;return}let g=await p.json();if(Sr(g.total),a.innerHTML="",g.results.length===0){a.innerHTML="<div>No results found</div>",en();return}let m=Array.isArray(g.highlight_terms)?g.highlight_terms:[],v=g.total>20?` (page ${Math.floor(Wt()/20)+1})`:"";a.innerHTML=`<div class="results-header">Found ${g.total} results in ${Math.round(g.search_time_ms)}ms${v}</div>`,g.results.forEach((y,x)=>{let b=document.createElement("div"),j=y.source==="WSL";b.className=`result ${j?"wsl":"windows"}`,b.style.animationDelay=`${x*.04}s`,b.id=`result-${x}`,b.dataset.conversationId=y.conversation_id,typeof y.message_start_index=="number"&&(b.dataset.messageStart=String(y.message_start_index)),typeof y.message_end_index=="number"&&(b.dataset.messageEnd=String(y.message_end_index));let V=y.conversation_id.split("-").pop(),B=y.tool||"claude",U=Br(B),E=Zt(y.title,r,m),S=oi(y.snippet,r,m),_=De(),C=_?`<button class="resume-btn" data-conversation-id="${y.conversation_id}" disabled title="Disabled in snapshot mode (${oe(_)})">\u26A1 Resume (disabled)</button>`:`<button class="resume-btn" data-conversation-id="${y.conversation_id}">\u26A1 Resume Session</button>`;b.innerHTML=`
            <div class="result-title">${E}</div>
            <div class="result-meta">
                <span class="tool-badge ${B}">${U}</span> \u2022
                <span class="conv-id">...${V}</span> \u2022
                ${y.project_id} \u2022
                ${y.message_count} msgs \u2022
                ${new Date(y.updated_at).toLocaleDateString()}
            </div>
            <div class="result-snippet">${S}</div>
            <div class="result-actions">
                ${C}
                <button class="diff-btn" data-conversation-id="${y.conversation_id}">
                    View Diff
                </button>
            </div>
            <div class="result-diff" data-loaded="false"></div>
        `,zt(b,y.conversation_id);let w=b.querySelector(".result-title"),k=mr(y.conversation_id);w.appendChild(k);let L=b.querySelector(".resume-btn");L&&!pt()&&L.addEventListener("click",z=>{z.stopPropagation(),Ye(y.conversation_id,L)}),b.onclick=()=>{en(),sessionStorage.setItem("lastScrollPosition",window.scrollY),sessionStorage.setItem("lastResultIndex",x),sessionStorage.setItem("activeConversationId",y.conversation_id),Ee(y.conversation_id)},a.appendChild(b)}),_r(a,xe),ii(a),To({query:r,mode:document.getElementById("mode").value,project:document.getElementById("project").value,tool:o,date:document.getElementById("date").value,dateFrom:document.getElementById("date").value==="custom"?document.getElementById("dateFrom").value:"",dateTo:document.getElementById("date").value==="custom"?document.getElementById("dateTo").value:"",sortBy:document.getElementById("sortBy").value}),en()}function Y(){let e=document.getElementById("conversationHeader"),t=document.getElementById("heroTitle"),n=document.getElementById("heroSubtitle"),r=document.getElementById("filters"),s=document.getElementById("chatPanel"),o=document.getElementById("results");if(e&&(e.style.display="none"),r&&(r.style.display=""),s&&(s.style.display="block"),sessionStorage.removeItem("activeConversationId"),o){o.innerHTML="";let i=sessionStorage.getItem("lastView"),a=!!sessionStorage.getItem("searchState"),l=!!sessionStorage.getItem("allConversationsState");i||a||l?o.innerHTML='<div class="loading">Restoring results...</div>':o.innerHTML="<div>Enter a search query or select a filter</div>"}}function nn(){let e=document.getElementById("date"),t=document.getElementById("customDateRange");t.style.display=e.value==="custom"?"inline":"none"}async function Ye(e,t){if(pt()){console.error("Resume is disabled in snapshot mode");return}let n=t.innerHTML;t.innerHTML="\u23F3 Opening...",t.disabled=!0;try{let r=await fetch("/api/resume",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_id:e})}),s=await r.json();if(r.ok&&s.success)t.innerHTML="\u2713 Opened in terminal",t.classList.add("success"),setTimeout(()=>{t.innerHTML=n,t.classList.remove("success"),t.disabled=!1},2e3);else throw new Error(s.detail||"Failed to resume session")}catch(r){t.innerHTML="\u274C Failed - check console",t.classList.add("error"),console.error("Resume error:",r),setTimeout(()=>{t.innerHTML=n,t.classList.remove("error"),t.disabled=!1},3e3)}}async function gt(){let e=document.getElementById("results");e.innerHTML='<div class="loading">Loading all conversations...</div>',tn.clear(),$r=0;let t=document.getElementById("sortBy").value,n=document.getElementById("project").value,r=document.getElementById("tool").value,s=document.getElementById("date").value,o="length";t==="date_newest"?o="date_newest":t==="date_oldest"?o="date_oldest":t==="messages"&&(o="length");let i=new URLSearchParams({sort_by:o});if(n&&i.append("project",n),r?i.append("tool",r):n&&(n.startsWith("opencode-")?i.append("tool","opencode"):n.startsWith("vibe-")&&i.append("tool","vibe")),i.has("project")){let c=i.get("project")||"";c.startsWith("opencode-")?i.append("tool","opencode"):c.startsWith("vibe-")&&i.append("tool","vibe")}if(s&&(i.append("date",s),s==="custom")){let c=document.getElementById("dateFrom").value,u=document.getElementById("dateTo").value;c&&i.append("date_from",c),u&&i.append("date_to",u)}te(i);let a=50,l=Wt();i.set("limit",a),i.set("offset",l);try{let u=await(await fetch(`/api/conversations/all?${i}`)).json();if(e.innerHTML="",u.results.length===0){e.innerHTML="<div>No conversations found</div>";return}let d=n?` in project "${n}"`:"",h=s?` ${{today:"from today",week:"from last 7 days",month:"from last 30 days",custom:"from custom date range"}[s]||""}`:"",p=l+1,g=l+u.results.length;e.innerHTML=`<div class="results-header">Showing ${p}\u2013${g} of ${u.total} conversations${d}${h} (sorted by ${o})</div>`;let m=document.createDocumentFragment();u.results.forEach((v,y)=>{let x=l+y,b=document.createElement("div"),j=v.source==="WSL";b.className=`result ${j?"wsl":"windows"}`,b.style.animationDelay=`${y*.04}s`,b.id=`result-${x}`,b.dataset.conversationId=v.conversation_id;let V=v.conversation_id.split("-").pop(),B=v.tool||"claude",U=Br(B),E=oi(v.snippet,"",[]),S=De(),_=S?`<button class="resume-btn" data-conversation-id="${v.conversation_id}" disabled title="Disabled in snapshot mode (${oe(S)})">\u26A1 Resume (disabled)</button>`:`<button class="resume-btn" data-conversation-id="${v.conversation_id}">\u26A1 Resume Session</button>`;b.innerHTML=`
                <div class="result-title">${oe(v.title)}</div>
                <div class="result-meta">
                    <span class="tool-badge ${B}">${U}</span> \u2022
                    <span class="conv-id">...${V}</span> \u2022
                    ${v.project_id} \u2022
                    ${v.message_count} msgs \u2022
                    ${new Date(v.updated_at).toLocaleDateString()}
                </div>
                <div class="result-snippet">${E}</div>
                <div class="result-actions">
                    ${_}
                    <button class="diff-btn" data-conversation-id="${v.conversation_id}">
                        View Diff
                    </button>
                </div>
                <div class="result-diff" data-loaded="false"></div>
            `,zt(b,v.conversation_id);let C=b.querySelector(".result-title"),w=mr(v.conversation_id);C.appendChild(w);let k=b.querySelector(".resume-btn");k&&!pt()&&k.addEventListener("click",L=>{L.stopPropagation(),Ye(v.conversation_id,k)}),b.onclick=()=>{Ar(),sessionStorage.setItem("lastScrollPosition",window.scrollY),sessionStorage.setItem("lastResultIndex",x),sessionStorage.setItem("activeConversationId",v.conversation_id),Ee(v.conversation_id)},m.appendChild(b)}),e.appendChild(m),Sr(u.total),window.goToPage=v=>Jt(v,gt),_r(e,gt),Ar(),ii(e)}catch(c){e.innerHTML=`<div style="color: hsl(var(--danger));">Error: ${c.message}</div>`}}async function Ee(e,t=!0){if(!e){let d=sessionStorage.getItem("activeConversationId");if(d)e=d;else return}let n=document.getElementById("results"),r=document.getElementById("conversationHeader"),s=document.getElementById("heroTitle"),o=document.getElementById("heroSubtitle"),i=document.getElementById("filters"),a=document.getElementById("chatPanel");r&&(r.style.display="block"),s&&(s.style.display="none"),o&&(o.style.display="none"),i&&(i.style.display="none"),a&&(a.style.display="none");let l=document.querySelector("#conversationHeader .back-button");l&&(l.onclick=async d=>{d.preventDefault(),history.pushState({},"","/"),Y(),await ie()}),n.innerHTML="";let c=document.createElement("div");c.className="results-header",c.textContent=`Loading conversation ${e}...`,n.appendChild(c);let u=document.createElement("div");u.className="loading",u.textContent="Loading conversation...",n.appendChild(u);try{t&&history.pushState({conversationId:e},"",`/conversation/${e}`);let d=te(new URLSearchParams),f=d.toString()?`/api/conversation/${e}?${d.toString()}`:`/api/conversation/${e}`,h=await fetch(f);if(!h.ok){let I=await h.json().catch(()=>null),A=I&&I.detail?I.detail:"Failed to load conversation";n.innerHTML="";let J=document.createElement("div");J.style.color="hsl(var(--danger))",J.textContent=A,n.appendChild(J);return}let p=await h.json();c.textContent=`Loaded ${e} | messages: ${Array.isArray(p.messages)?p.messages.length:0}`;let g=p.tool||pd(p.file_path),m=Br(g),v=p.project_path||"",y=v?`Project: ${v}`:`Project: ${p.project_id||"Unknown"}`;n.innerHTML="";let x=document.createElement("div");x.className="header";let b=document.createElement("span");b.className=`tool-badge ${g}`,b.textContent=m;let j=document.createElement("h2");j.textContent=p.title||"No title available";let V=document.createElement("div");V.textContent=`${y} | Messages: ${p.message_count||0}`;let B=document.createElement("div");B.className="result-actions";let U=document.createElement("button");U.className="resume-btn",U.dataset.conversationId=p.conversation_id,pt()?(U.textContent="\u26A1 Resume (disabled)",U.disabled=!0,U.title=`Disabled in snapshot mode (${De()})`):(U.textContent="\u26A1 Resume Session",U.addEventListener("click",I=>{I.stopPropagation(),Ye(p.conversation_id,U)}));let E=document.createElement("div");E.style.cssText="position: relative; display: inline-block;";let S=document.createElement("button");S.className="export-btn",S.textContent="\u{1F4E5} Export",S.style.cssText=`
            background: hsl(var(--accent));
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-family: var(--font-sans);
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        `;let _=document.createElement("div");_.style.cssText=`
            display: none;
            position: absolute;
            right: 0;
            top: 100%;
            margin-top: 4px;
            background: hsl(var(--bg-elevated));
            border: 1px solid hsl(var(--border-glass));
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            min-width: 150px;
        `,[{value:"json",label:"\u{1F4C4} JSON",desc:"Structured data"},{value:"markdown",label:"\u{1F4DD} Markdown",desc:"Formatted text"},{value:"text",label:"\u{1F4C3} Plain Text",desc:"Simple text"}].forEach(I=>{let A=document.createElement("div");A.style.cssText=`
                padding: 10px 14px;
                cursor: pointer;
                transition: background 0.2s;
                border-bottom: 1px solid hsl(var(--border-subtle));
            `,A.innerHTML=`
                <div style="font-weight: 500; color: hsl(var(--text-primary)); margin-bottom: 2px;">
                    ${I.label}
                </div>
                <div style="font-size: 12px; color: hsl(var(--text-tertiary));">
                    ${I.desc}
                </div>
            `,A.addEventListener("mouseenter",()=>{A.style.background="hsl(var(--bg-surface))"}),A.addEventListener("mouseleave",()=>{A.style.background="transparent"}),A.addEventListener("click",()=>{bd(p.conversation_id,I.value),_.style.display="none"}),_.appendChild(A)}),_.lastChild.style.borderBottom="none",S.addEventListener("click",I=>{I.stopPropagation(),_.style.display=_.style.display==="none"?"block":"none"}),document.addEventListener("click",I=>{E.contains(I.target)||(_.style.display="none")}),E.appendChild(S),E.appendChild(_),B.appendChild(U),B.appendChild(E),x.appendChild(b),x.appendChild(j),x.appendChild(V),x.appendChild(B),n.appendChild(x);let w=document.createElement("div");w.className="conversation-tabs";let k=document.createElement("button");k.className="tab-button active",k.textContent="Messages";let L=document.createElement("button");L.className="tab-button",L.textContent="Code";let z=document.createElement("button");z.className="tab-button",z.textContent="Similar";let D=document.createElement("div");D.id="messagesContainer",D.style.display="block";let ne=document.createElement("div");ne.id="codeContainer",ne.style.display="none";let ae=document.createElement("div");ae.id="similarContainer",ae.style.display="none";let Se=(I,A)=>{[k,L,z].forEach(J=>{J.classList.remove("active")}),[D,ne,ae].forEach(J=>{J.style.display="none"}),I.classList.add("active"),A.style.display="block"};if(k.addEventListener("click",()=>{Se(k,D)}),L.addEventListener("click",()=>{Se(L,ne),ne.dataset.loaded||(Mo(e,ne),ne.dataset.loaded="true")}),z.addEventListener("click",()=>{Se(z,ae),ae.dataset.loaded||(jo(e,ae),ae.dataset.loaded="true")}),w.appendChild(k),w.appendChild(L),w.appendChild(z),n.appendChild(w),n.appendChild(D),n.appendChild(ne),n.appendChild(ae),p.messages&&Array.isArray(p.messages)&&p.messages.length>0)p.messages.forEach((I,A)=>{let J=document.createElement("div");J.className=`message ${I.role||"unknown"}`;let de=document.createElement("div");de.className="message-header";let nt=document.createElement("div");nt.className="role",nt.textContent=`${(I.role||"unknown").toUpperCase()} - Message ${A+1}`;let T=document.createElement("div");T.className="message-actions";let H=document.createElement("button");H.className="message-copy",H.type="button",H.textContent="Copy",H.addEventListener("click",async ta=>{ta.stopPropagation(),await yd(I.content||"",H)}),T.appendChild(H),de.appendChild(nt),de.appendChild(T);let G=document.createElement("div");G.className="content",G.textContent=I.content||"",J.appendChild(de),J.appendChild(G),D.appendChild(J)});else{let I=document.createElement("div");I.className="message",I.textContent="No messages available",D.appendChild(I)}sessionStorage.setItem("activeConversationId",e)}catch(d){n.innerHTML="";let f=document.createElement("div");f.style.color="hsl(var(--danger))",f.textContent=`Error: ${d.message}`,n.appendChild(f)}}function bd(e,t){let n=document.createElement("a"),r=new URLSearchParams({format:t});te(r),n.href=`/api/conversation/${e}/export?${r.toString()}`,n.download=`conversation-${e}.${t==="markdown"?"md":t}`,document.body.appendChild(n),n.click(),document.body.removeChild(n)}var Tr,tn,$r,ti,we=M(()=>{Ge();ur();pr();vr();qo();Er();Cr();kr();Ke();Ir();Tr=0,tn=new Map,$r=0,ti=!1});function en(){let e={query:document.getElementById("search").value,mode:document.getElementById("mode").value,project:document.getElementById("project").value,tool:document.getElementById("tool").value,date:document.getElementById("date").value,dateFrom:document.getElementById("dateFrom").value,dateTo:document.getElementById("dateTo").value,sortBy:document.getElementById("sortBy").value};sessionStorage.setItem("searchState",JSON.stringify(e)),sessionStorage.setItem("lastView","search")}function Ar(){let e={project:document.getElementById("project").value,tool:document.getElementById("tool").value,date:document.getElementById("date").value,dateFrom:document.getElementById("dateFrom").value,dateTo:document.getElementById("dateTo").value,sortBy:document.getElementById("sortBy").value};sessionStorage.setItem("allConversationsState",JSON.stringify(e)),sessionStorage.setItem("lastView","all")}async function ie(){if(sessionStorage.getItem("lastView")==="all"){let o=sessionStorage.getItem("allConversationsState");if(!o)return!1;let i=JSON.parse(o);document.getElementById("project").value=i.project||"",document.getElementById("tool").value=i.tool||"",document.getElementById("date").value=i.date||"",document.getElementById("dateFrom").value=i.dateFrom||"",document.getElementById("dateTo").value=i.dateTo||"",document.getElementById("sortBy").value=i.sortBy||"relevance";let{toggleCustomDate:a,showAllConversations:l}=await Promise.resolve().then(()=>(we(),rn));return a(),await l(),!0}let t=sessionStorage.getItem("searchState");if(!t)return!1;let n=JSON.parse(t);document.getElementById("search").value=n.query||"",document.getElementById("mode").value=n.mode||"hybrid",document.getElementById("project").value=n.project||"",document.getElementById("tool").value=n.tool||"",document.getElementById("date").value=n.date||"",document.getElementById("dateFrom").value=n.dateFrom||"",document.getElementById("dateTo").value=n.dateTo||"",document.getElementById("sortBy").value=n.sortBy||"relevance";let{toggleCustomDate:r}=await Promise.resolve().then(()=>(we(),rn));if(r(),!!(n.query||n.project||n.tool||n.date||n.dateFrom||n.dateTo)){let{search:o}=await Promise.resolve().then(()=>(we(),rn));return o(),!0}return!1}var Ge=M(()=>{});function ai(){document.addEventListener("keydown",xd),Ed()}function xd(e){let t=document.activeElement,n=t.tagName==="INPUT"||t.tagName==="TEXTAREA"||t.isContentEditable;if(e.key==="?"&&e.shiftKey){e.preventDefault(),yt();return}if(e.key==="Escape"){if(vt){e.preventDefault(),yt();return}if(n&&t.id==="search"){e.preventDefault(),t.value="";return}return}if(!(n&&t.id!=="search")){if(e.key==="/"){e.preventDefault();let r=document.getElementById("search");r&&(r.focus(),r.select());return}if(e.key==="r"&&!n){e.preventDefault(),window.resumeSession&&window.resumeSession();return}if(e.key==="c"&&!n){e.preventDefault();let r=document.getElementById("chatQuestion");r&&(r.focus(),r.select());return}}}function Ed(){let e=document.createElement("div");e.id="shortcutsHelpModal",e.style.cssText=`
        display: none;
        position: fixed;
        z-index: 10000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        animation: fadeIn 0.2s ease;
    `,e.innerHTML=`
        <div style="
            position: relative;
            background: hsl(var(--bg-base));
            margin: 10% auto;
            padding: 32px;
            border-radius: 12px;
            max-width: 600px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h2 style="margin: 0; color: hsl(var(--text-primary)); font-family: var(--font-sans);">
                    \u2328\uFE0F Keyboard Shortcuts
                </h2>
                <button onclick="window.toggleHelpModal()" style="
                    background: transparent;
                    border: none;
                    font-size: 28px;
                    cursor: pointer;
                    color: hsl(var(--text-tertiary));
                    padding: 0;
                    width: 32px;
                    height: 32px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 4px;
                    transition: all 0.2s;
                " onmouseover="this.style.background='hsl(var(--bg-surface))'" onmouseout="this.style.background='transparent'">
                    \xD7
                </button>
            </div>

            <div style="display: grid; gap: 16px;">
                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">?</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Show this help dialog</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">/</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Focus search box</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">Esc</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Clear search / Close dialog</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">r</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Resume last conversation</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">c</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Focus chat input</span>
                </div>

                <div class="shortcut-item">
                    <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 13px;
                        border: 1px solid hsl(var(--border-glass));
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    ">Enter</kbd>
                    <span style="margin-left: 16px; color: hsl(var(--text-primary));">Search (when in search box)</span>
                </div>
            </div>

            <div style="margin-top: 24px; padding-top: 20px; border-top: 1px solid hsl(var(--border-subtle)); color: hsl(var(--text-tertiary)); font-size: 13px;">
                <p style="margin: 0;">
                    \u{1F4A1} <strong>Tip:</strong> Most shortcuts work from anywhere on the page. Press <kbd style="
                        background: hsl(var(--bg-surface));
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 12px;
                    ">Esc</kbd> to close this dialog.
                </p>
            </div>
        </div>
    `;let t=document.createElement("style");t.textContent=`
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideIn {
            from {
                transform: translateY(-50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .shortcut-item {
            display: flex;
            align-items: center;
            padding: 8px 0;
        }
    `,document.head.appendChild(t),e.addEventListener("click",n=>{n.target===e&&yt()}),document.body.appendChild(e)}function yt(){let e=document.getElementById("shortcutsHelpModal");e&&(vt=!vt,e.style.display=vt?"block":"none",document.body.style.overflow=vt?"hidden":"")}var vt,li=M(()=>{vt=!1});function ui(){let e=document.getElementById("search");if(!e)return;let t=document.createElement("div");t.id="suggestionsContainer",t.style.cssText=`
        position: absolute;
        display: none;
        background: hsl(var(--bg-elevated));
        border: 1px solid hsl(var(--border-glass));
        border-radius: 8px;
        margin-top: 4px;
        max-height: 300px;
        overflow-y: auto;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        min-width: 400px;
    `,e.parentNode.style.position="relative",e.parentNode.appendChild(t),e.addEventListener("input",n=>{let r=n.target.value.trim();if(r.length<2){Oe();return}clearTimeout(ci),ci=setTimeout(()=>{wd(r)},300)}),e.addEventListener("keydown",n=>{let r=document.getElementById("suggestionsContainer");if(!r||r.style.display==="none")return;let s=r.querySelectorAll(".suggestion-item");s.length!==0&&(n.key==="ArrowDown"?(n.preventDefault(),me=Math.min(me+1,s.length-1),di(s)):n.key==="ArrowUp"?(n.preventDefault(),me=Math.max(me-1,-1),di(s)):n.key==="Enter"&&me>=0?(n.preventDefault(),s[me].click()):n.key==="Escape"&&Oe())}),document.addEventListener("click",n=>{let r=document.getElementById("search"),s=document.getElementById("suggestionsContainer");r&&s&&!r.contains(n.target)&&!s.contains(n.target)&&Oe()})}async function wd(e){if(document.getElementById("suggestionsContainer"))try{let n=await fetch(`/api/search/suggestions?q=${encodeURIComponent(e)}&limit=10`);if(!n.ok){Oe();return}let r=await n.json();if(!r.suggestions||r.suggestions.length===0){Oe();return}Sd(r.suggestions,e)}catch(n){console.error("Failed to fetch suggestions:",n),Oe()}}function Sd(e,t){let n=document.getElementById("suggestionsContainer");if(!n)return;me=-1;let r=`
        <div style="
            padding: 8px 12px;
            border-bottom: 1px solid hsl(var(--border-subtle));
            color: hsl(var(--text-tertiary));
            font-size: 12px;
            font-weight: 500;
        ">
            SUGGESTIONS
        </div>
    `;e.forEach((s,o)=>{let i=_d(s,t);r+=`
            <div class="suggestion-item" data-suggestion="${bt(s)}" style="
                padding: 10px 12px;
                cursor: pointer;
                transition: background 0.2s;
                border-bottom: 1px solid hsl(var(--border-subtle));
                color: hsl(var(--text-primary));
                font-size: 14px;
            " onmouseover="this.style.background='hsl(var(--bg-surface))'" onmouseout="this.style.background='transparent'">
                ${i}
            </div>
        `}),r=r.replace(/border-bottom: 1px solid hsl\(var\(--border-subtle\)\);(?![\s\S]*border-bottom)/,""),n.innerHTML=r,n.style.display="block",n.querySelectorAll(".suggestion-item").forEach(s=>{s.addEventListener("click",()=>{let o=document.getElementById("search");o&&(o.value=s.dataset.suggestion,Oe(),window.search&&window.search())})})}function _d(e,t){let n=e.toLowerCase().indexOf(t.toLowerCase());if(n===-1)return bt(e);let r=bt(e.substring(0,n)),s=bt(e.substring(n,n+t.length)),o=bt(e.substring(n+t.length));return`${r}<strong style="color: hsl(var(--accent)); font-weight: 600;">${s}</strong>${o}`}function di(e){e.forEach((t,n)=>{if(n===me){t.style.background="hsl(var(--bg-surface))",t.scrollIntoView({block:"nearest"});let r=document.getElementById("search");r&&(r.value=t.dataset.suggestion)}else t.style.background="transparent"})}function Oe(){let e=document.getElementById("suggestionsContainer");e&&(e.style.display="none"),me=-1}function bt(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}var ci,me,fi=M(()=>{ci=null,me=-1});async function pi(){let e=document.getElementById("results"),t=document.getElementById("filters"),n=[document.getElementById("heroTitle"),document.getElementById("heroSubtitle"),document.getElementById("search")];t.style.display="none",n.forEach(r=>{r&&(r.style.display="none")}),e.innerHTML='<div class="loading">Loading analytics...</div>',await hi(e,30)}async function hi(e,t){try{let[n,r,s,o,i,a,l,c]=await Promise.all([fetch("/api/stats/analytics/config"),fetch(`/api/stats/analytics/summary?days=${t}`),fetch(`/api/stats/analytics/top-queries?limit=10&days=${t}`),fetch(`/api/stats/analytics/dead-ends?limit=10&days=${t}`),fetch(`/api/stats/analytics/trends?days=${t}`),fetch(`/api/stats/analytics/heatmap?days=${t}`),fetch(`/api/stats/analytics/agent-comparison?days=${t}`),fetch(`/api/stats/analytics/topics?days=${t}&k=8`)]),u=await n.json(),d=await r.json(),f=await s.json(),h=await o.json(),p=await i.json(),g=await a.json(),m=await l.json(),v=await c.json();e.innerHTML=`
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; gap: 12px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">
                        <h2 style="margin: 0; font-size: 28px; color: hsl(var(--text-primary));">Search Analytics</h2>
                        <div style="display: inline-flex; align-items: center; gap: 8px; color: hsl(var(--text-secondary)); font-size: 13px;">
                            <span>Range:</span>
                            <select id="analyticsDays" class="glass-select">
                                <option value="7" ${t===7?"selected":""}>7 days</option>
                                <option value="30" ${t===30?"selected":""}>30 days</option>
                                <option value="90" ${t===90?"selected":""}>90 days</option>
                            </select>
                            <button id="analyticsRefresh" class="glass-btn">Refresh</button>
                        </div>
                    </div>
                    <a href="/" style="color: hsl(var(--accent)); text-decoration: none; font-weight: 500;">\u2190 Back to Search</a>
                </div>

                ${Cd(u)}

                <!-- Summary Cards -->
                <div class="stat-grid" style="margin-bottom: 40px;">
                    ${sn("Total Searches",d.total_searches)}
                    ${sn("Unique Queries",d.unique_queries)}
                    ${sn("Avg Results",d.avg_results)}
                    ${sn("Avg Time (ms)",d.avg_time_ms)}
                </div>

                <!-- Search Mode Distribution -->
                ${kd(d.mode_distribution)}

                <!-- Top Queries -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Top Searches (Last ${t} Days)</div>
                    ${Id(f.queries)}
                </div>

                <!-- Dead End Queries -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Dead End Searches</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Queries that returned 3 or fewer results</p>
                    ${Td(h.queries)}
                </div>

                <!-- Trends -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Trends (Last ${t} Days)</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Daily searches and average latency</p>
                    ${Ad(p.points)}
                </div>

                <!-- Heatmap -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Heatmap</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Search activity by day-of-week and hour-of-day (UTC)</p>
                    ${$d(g.cells)}
                </div>

                <!-- Agent Comparison -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Tool Filter Comparison</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">How often you search within a specific tool filter</p>
                    ${Ld(m.tools)}
                </div>

                <!-- Topic Clusters -->
                <div class="glass">
                    <div class="card-title">Topics</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Clusters of repeated query themes</p>
                    ${Bd(v.clusters)}
                </div>
            </div>
        `;let y=document.getElementById("analyticsDays"),x=document.getElementById("analyticsRefresh"),b=async()=>{let j=y?Number.parseInt(y.value,10):30;e.innerHTML='<div class="loading">Loading analytics...</div>',await hi(e,Number.isFinite(j)?j:30)};y&&y.addEventListener("change",b),x&&x.addEventListener("click",b)}catch(n){e.innerHTML=`
            <div style="text-align: center; padding: 40px; color: hsl(var(--danger));">
                Failed to load analytics: ${n.message}
                <br><br>
                <a href="/" style="color: hsl(var(--accent));">\u2190 Back to Search</a>
            </div>
        `}}function Cd(e){return!e||e.enabled!==!1?"":`
        <div style="background: hsl(var(--warning) / 0.1); border: 1px solid hsl(var(--warning) / 0.25); border-radius: var(--radius-lg); padding: 16px 18px; margin-bottom: 20px;">
            <div style="font-weight: 700; color: hsl(var(--text-primary)); margin-bottom: 6px;">Analytics tracking is disabled</div>
            <div style="color: hsl(var(--text-secondary)); font-size: 13px; line-height: 1.4;">
                Searches are not being logged. Enable <code>[analytics].enabled = true</code> in <code>~/.searchat/config/settings.toml</code>
                (or set <code>SEARCHAT_ENABLE_ANALYTICS=1</code>) to start collecting analytics.
            </div>
        </div>
    `}function sn(e,t){return`
        <div class="stat-card">
            <div class="stat-label">${e}</div>
            <div class="stat-value neutral">${Hd(t)}</div>
        </div>
    `}function kd(e){if(!e||Object.keys(e).length===0)return"";let t=Object.values(e).reduce((s,o)=>s+o,0),n=Object.entries(e).map(([s,o])=>({mode:s,count:o,percentage:(o/t*100).toFixed(1)})),r={hybrid:"var(--chart-1)",semantic:"var(--chart-4)",keyword:"var(--chart-2)"};return`
        <div class="glass" style="margin-bottom: 24px;">
            <div class="card-title">Search Mode Distribution</div>
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                ${n.map(s=>`
                    <div class="stat-card" style="flex: 1; min-width: 150px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: ${r[s.mode]||"hsl(var(--text-tertiary))"};"></div>
                            <div style="font-weight: 600; color: hsl(var(--text-primary)); text-transform: capitalize;">${s.mode}</div>
                        </div>
                        <div class="stat-value">${s.count}</div>
                        <div class="stat-sub">${s.percentage}% of searches</div>
                    </div>
                `).join("")}
            </div>
        </div>
    `}function Id(e){return!e||e.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available yet. Start searching to see analytics!</div>':`
        <div style="display: grid; gap: 12px;">
            ${e.map((t,n)=>`
                <div class="glass" style="display: flex; align-items: center; gap: 16px; padding: 12px;">
                    <div style="font-size: 18px; font-weight: 700; color: hsl(var(--text-tertiary)); min-width: 30px;">#${n+1}</div>
                    <div style="flex: 1;">
                        <div style="font-family: var(--font-mono); font-size: 14px; color: hsl(var(--text-primary)); margin-bottom: 4px;">${Ze(t.query)}</div>
                        <div style="font-size: 12px; color: hsl(var(--text-tertiary));">
                            ${t.search_count} searches \xB7 ${t.avg_results} avg results \xB7 ${t.avg_time_ms}ms avg time
                        </div>
                    </div>
                    <button onclick="window.location.href = '/?q=${encodeURIComponent(t.query)}'" class="glass-btn glass-btn-primary" style="font-size: 12px; padding: 8px 16px;">
                        Search Again
                    </button>
                </div>
            `).join("")}
        </div>
    `}function Td(e){return!e||e.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No dead ends found!</div>':`
        <div style="display: grid; gap: 12px;">
            ${e.map((t,n)=>`
                <div class="glass" style="display: flex; align-items: center; gap: 16px; padding: 12px;">
                    <div style="font-size: 18px; font-weight: 700; color: hsl(var(--text-tertiary)); min-width: 30px;">#${n+1}</div>
                    <div style="flex: 1;">
                        <div style="font-family: var(--font-mono); font-size: 14px; color: hsl(var(--text-primary)); margin-bottom: 4px;">${Ze(t.query)}</div>
                        <div style="font-size: 12px; color: hsl(var(--text-tertiary));">
                            ${t.search_count} searches \xB7 ${t.avg_results} avg results
                        </div>
                    </div>
                    <span class="badge badge-warn">Low Results</span>
                </div>
            `).join("")}
        </div>
    `}function Ad(e){if(!e||e.length===0)return'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available yet.</div>';let t=Math.max(...e.map(a=>a.searches||0),1),n=900,r=120,s=10,o=Math.max(2,Math.floor((n-s*2)/e.length)),i=e.map((a,l)=>{let c=Math.round((a.searches||0)/t*(r-s*2)),u=s+l*o,d=r-s-c;return`<rect x="${u}" y="${d}" width="${o-1}" height="${c}" fill="var(--chart-1)" opacity="0.85"></rect>`}).join("");return`
        <div style="overflow-x: auto;">
            <svg width="${n}" height="${r}" viewBox="0 0 ${n} ${r}" role="img" aria-label="Search trend bars">
                ${i}
            </svg>
        </div>
    `}function $d(e){if(!e||e.length===0)return'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available yet.</div>';let t=new Map,n=1;for(let a of e){let l=`${a.dow}-${a.hour}`;t.set(l,a.searches),a.searches>n&&(n=a.searches)}let r=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"],s=Array.from({length:24},(a,l)=>l),o=`
        <div style="display: grid; grid-template-columns: 46px repeat(24, 1fr); gap: 3px; align-items: center; margin-bottom: 8px;">
            <div></div>
            ${s.map(a=>`<div style="font-size: 10px; color: hsl(var(--text-tertiary)); text-align: center;">${a}</div>`).join("")}
        </div>
    `,i=r.map((a,l)=>{let c=s.map(u=>{let d=t.get(`${l}-${u}`)||0,f=d===0?.08:.15+.75*(d/n);return`<div title="${a} ${u}:00 \u2014 ${d} searches" style="height: 14px; border-radius: 3px; background: hsl(var(--accent) / ${f.toFixed(3)}); border: 1px solid hsl(var(--border-subtle));"></div>`}).join("");return`
            <div style="display: grid; grid-template-columns: 46px repeat(24, 1fr); gap: 3px; align-items: center; margin-bottom: 3px;">
                <div style="font-size: 11px; color: hsl(var(--text-tertiary));">${a}</div>
                ${c}
            </div>
        `}).join("");return`<div style="overflow-x: auto;">${o}${i}</div>`}function Ld(e){return!e||e.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available yet.</div>':`
        <div style="display: grid; gap: 10px;">
            ${e.map(t=>`
                <div class="glass" style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px;">
                    <div>
                        <div style="font-weight: 700; color: hsl(var(--text-primary)); text-transform: uppercase;">${Ze(t.tool_filter)}</div>
                        <div style="font-size: 12px; color: hsl(var(--text-tertiary));">${t.searches} searches \xB7 ${t.avg_time_ms}ms avg time \xB7 ${t.avg_results} avg results</div>
                    </div>
                    <button onclick="window.location.href='${t.tool_filter==="all"?"/":`/?tool=${encodeURIComponent(t.tool_filter)}`}'" class="glass-btn">
                        Filter
                    </button>
                </div>
            `).join("")}
        </div>
    `}function Bd(e){return!e||e.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">Not enough data to cluster topics yet.</div>':`
        <div style="display: grid; gap: 12px;">
            ${e.map(t=>`
                <div class="glass" style="padding: 14px;">
                    <div style="display: flex; justify-content: space-between; gap: 12px; align-items: baseline;">
                        <div style="font-weight: 800; color: hsl(var(--text-primary));">${Ze((t.top_terms||[]).join(", ")||"topic")}</div>
                        <div style="color: hsl(var(--text-tertiary)); font-size: 12px;">${t.searches} searches</div>
                    </div>
                    <div style="margin-top: 6px; font-family: var(--font-mono); font-size: 12px; color: hsl(var(--text-tertiary));">
                        ${Ze(t.representative_query||"")}
                    </div>
                    ${t.examples&&t.examples.length?`
                        <div style="margin-top: 8px; color: hsl(var(--text-tertiary)); font-size: 12px;">
                            Examples: ${Ze(t.examples.join(" \xB7 "))}
                        </div>
                    `:""}
                </div>
            `).join("")}
        </div>
    `}function Hd(e){return e>=1e3?(e/1e3).toFixed(1)+"k":e.toString()}function Ze(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}var mi=M(()=>{});function on(e){let t=document.createElement("div");return t.textContent=e,t.innerHTML}function Md(){try{let e=localStorage.getItem(bi);return e?JSON.parse(e):[]}catch(e){return console.error("Failed to load saved queries from local storage",e),[]}}function Rd(e){localStorage.setItem(bi,JSON.stringify(e))}function et(e){let t=document.getElementById("savedQueriesStatus");t&&(t.textContent=e||"")}function gi(){return{query:document.getElementById("search").value,mode:document.getElementById("mode").value,filters:{project:document.getElementById("project").value,tool:document.getElementById("tool").value,date:document.getElementById("date").value,date_from:document.getElementById("dateFrom").value,date_to:document.getElementById("dateTo").value,sort_by:document.getElementById("sortBy").value}}}function Dd(e){document.getElementById("search").value=e.query||"",document.getElementById("mode").value=e.mode||"hybrid",document.getElementById("project").value=e.filters?.project||"",document.getElementById("tool").value=e.filters?.tool||"",document.getElementById("date").value=e.filters?.date||"",document.getElementById("sortBy").value=e.filters?.sort_by||"relevance",document.getElementById("dateFrom").value=e.filters?.date_from||"",document.getElementById("dateTo").value=e.filters?.date_to||"",typeof window.toggleCustomDate=="function"&&window.toggleCustomDate()}function Od(){let e=document.getElementById("savedQueriesList");if(!e)return;if(!ce.length){e.innerHTML='<div class="saved-queries-status">No saved queries yet.</div>';return}let t=[];for(let n of ce){let r=n.description?` - ${on(n.description)}`:"",s=n.mode?on(n.mode):"",o=n.filters?.project?` \u2022 ${on(n.filters.project)}`:"",i=`${s}${o}`,a=n.synced===!1?" (local only)":"";t.push(`
            <div class="saved-query-item" data-query-id="${n.id}">
                <div class="saved-query-title">${on(n.name)}${a}</div>
                <div class="saved-query-meta">${i}${r}</div>
                <div class="saved-query-actions">
                    <button class="saved-query-run" data-query-id="${n.id}">Run</button>
                    <button class="saved-query-edit" data-query-id="${n.id}">Edit</button>
                    <button class="saved-query-delete" data-query-id="${n.id}">Delete</button>
                </div>
            </div>
        `)}e.innerHTML=t.join("")}function vi(e){an=e;let t=document.getElementById("savedQueriesForm");t&&(t.style.display="grid"),document.getElementById("savedQueryName").value=e?.name||"",document.getElementById("savedQueryDescription").value=e?.description||""}function yi(){an=null;let e=document.getElementById("savedQueriesForm");e&&(e.style.display="none"),document.getElementById("savedQueryName").value="",document.getElementById("savedQueryDescription").value=""}async function Pd(){try{let e=await fetch("/api/queries");if(!e.ok){let r=await e.json().catch(function(){return null});throw new Error(r?.detail||"Failed to load saved queries")}let t=await e.json();if(!Array.isArray(t.queries))return[];let n=[];for(let r of t.queries)n.push({...r,synced:!0});return n}catch{return et("Saved queries are available locally only."),null}}async function jd(e){let t=await fetch("/api/queries",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)});if(!t.ok){let r=await t.json().catch(function(){return null});throw new Error(r?.detail||"Failed to save query")}return(await t.json()).query}async function qd(e,t){let n=await fetch(`/api/queries/${e}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(t)});if(!n.ok){let s=await n.json().catch(function(){return null});throw new Error(s?.detail||"Failed to update query")}return(await n.json()).query}async function Nd(e){let t=await fetch(`/api/queries/${e}`,{method:"DELETE"});if(!t.ok){let n=await t.json().catch(function(){return null});throw new Error(n?.detail||"Failed to delete query")}}async function Fd(e){await fetch(`/api/queries/${e}/run`,{method:"POST"})}function Pe(e){ce=e,Rd(ce),Od()}function Vd(e){for(let t of ce)if(t.id===e)return t;return null}async function xi(){let e=["savedQueryCancel","savedQuerySave","savedQueriesList","savedQueryName","savedQueryDescription"];for(let u of e)if(!document.getElementById(u)){console.error(`Saved queries UI missing element: #${u}`);return}let t=Md(),n=await Pd();n?(Pe(n),et("")):Pe(t);let r=[],s=document.getElementById("saveQueryButton"),o=document.getElementById("saveQueryButtonInline");s&&r.push(s),o&&r.push(o);function i(){vi(gi())}for(let u of r)u.addEventListener("click",i);function a(){yi()}document.getElementById("savedQueryCancel").addEventListener("click",a);async function l(){let u=document.getElementById("savedQueryName").value.trim();if(!u){et("Name is required to save a query.");return}let d=document.getElementById("savedQueryDescription").value.trim(),f=an||gi(),h={name:u,description:d||null,query:f.query,filters:f.filters,mode:f.mode};try{if(f.id){let p=await qd(f.id,h),g=[];for(let m of ce)m.id===f.id?g.push({...p,synced:!0}):g.push(m);Pe(g)}else{let p=`local-${Date.now()}`,g={...h,id:p,created_at:new Date().toISOString(),last_used:null,use_count:0,synced:!1};Pe([g,...ce]);let m=await jd(h),v=[];for(let y of ce)y.id===p?v.push({...m,synced:!0}):v.push(y);Pe(v)}et(""),yi()}catch(p){et(p.message)}}document.getElementById("savedQuerySave").addEventListener("click",l);async function c(u){let d=u.target;if(!d.dataset.queryId)return;let f=d.dataset.queryId,h=Vd(f);if(h){if(d.classList.contains("saved-query-run")){Dd(h),window.search();let p=[];for(let g of ce)g.id===f?p.push({...g,last_used:new Date().toISOString(),use_count:(g.use_count||0)+1}):p.push(g);Pe(p),f.startsWith("local-")||Fd(f).catch(function(){return null})}if(d.classList.contains("saved-query-edit")&&(vi(h),an.id=h.id),d.classList.contains("saved-query-delete")){let p=[];for(let g of ce)g.id!==f&&p.push(g);if(Pe(p),!f.startsWith("local-"))try{await Nd(f)}catch(g){et(g.message)}}}}document.getElementById("savedQueriesList").addEventListener("click",c)}var bi,ce,an,Ei=M(()=>{bi="savedQueries",ce=[],an=null});function fn(){Et&&(clearInterval(Et),Et=null),un=null,Hr=null}function P(e){let t=document.createElement("div");return t.textContent=e||"",t.innerHTML}function Ud(){let e=document.getElementById("filters"),t=[document.getElementById("heroTitle"),document.getElementById("heroSubtitle"),document.getElementById("search")],n=document.getElementById("chatPanel");e&&(e.style.display="none"),t.forEach(r=>{r&&(r.style.display="none")}),n&&(n.style.display="none"),sessionStorage.setItem("lastView","dashboard")}async function zd(){let e=await fetch("/api/status/features");return e.ok?e.json():null}async function ln(){let e=await fetch("/api/dashboards");if(!e.ok){let t=await e.json().catch(()=>null);throw new Error(t?.detail||"Failed to load dashboards")}return e.json()}async function Wd(e){let t=await fetch(`/api/dashboards/${e}`);if(!t.ok){let n=await t.json().catch(()=>null);throw new Error(n?.detail||"Failed to load dashboard")}return t.json()}async function cn(){let e=await fetch("/api/queries");if(!e.ok){let t=await e.json().catch(()=>null);throw new Error(t?.detail||"Failed to load saved queries")}return e.json()}async function Jd(e){let t=await fetch("/api/dashboards",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)});if(!t.ok){let n=await t.json().catch(()=>null);throw new Error(n?.detail||"Failed to create dashboard")}return t.json()}async function Kd(e,t){let n=await fetch(`/api/dashboards/${e}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(t)});if(!n.ok){let r=await n.json().catch(()=>null);throw new Error(r?.detail||"Failed to update dashboard")}return n.json()}async function Xd(e){let t=await fetch(`/api/dashboards/${e}`,{method:"DELETE"});if(!t.ok){let n=await t.json().catch(()=>null);throw new Error(n?.detail||"Failed to delete dashboard")}}async function xt(e,t){t.innerHTML='<div class="dashboard-loading">Loading dashboard...</div>';let n=await fetch(`/api/dashboards/${e}/render`);if(!n.ok){let l=await n.json().catch(()=>null);throw new Error(l?.detail||"Failed to render dashboard")}let r=await n.json(),s=r.dashboard||{},o=Array.isArray(r.widgets)?r.widgets:[],i=Number.isFinite(s.refresh_interval)?s.refresh_interval:null,a=o.map(l=>{let c=Array.isArray(l.results)?l.results:[],u=c.length?c.map(d=>`
                <div class="dashboard-result-item">
                    <div class="dashboard-result-main">
                        <div class="dashboard-result-title">${P(d.title||"Untitled")}</div>
                        <div class="dashboard-result-meta">${P(d.project_id||"unknown")} \xB7 ${P(d.tool||"")} \xB7 ${d.message_count||0} msgs</div>
                        <div class="dashboard-result-snippet">${P(d.snippet||"")}</div>
                    </div>
                    <a class="dashboard-result-open" href="/conversation/${d.conversation_id}" data-conversation-id="${d.conversation_id}">Open</a>
                </div>
            `).join(""):'<div class="dashboard-empty">No results yet.</div>';return`
            <div class="dashboard-widget">
                <div class="dashboard-widget-header">
                    <div>
                        <div class="dashboard-widget-title">${P(l.title||"Saved Query")}</div>
                        <div class="dashboard-widget-meta">${P(l.query||"")} \xB7 ${l.total||0} results</div>
                    </div>
                    <div class="dashboard-widget-tag">${P(l.mode||"hybrid")}</div>
                </div>
                <div class="dashboard-widget-body">${u}</div>
            </div>
        `}).join("");t.innerHTML=`
        <div class="dashboard-view-header">
            <div>
                <h2>${P(s.name||"Dashboard")}</h2>
                <p>${P(s.description||"")}</p>
                ${i?`<p style="margin-top: 6px; font-size: 12px; color: hsl(var(--text-tertiary));">Auto-refresh: every ${i}s</p>`:""}
            </div>
            <div class="dashboard-view-actions">
                <button class="secondary" data-action="refresh" data-dashboard-id="${e}">Refresh</button>
                <button class="secondary" data-action="edit" data-dashboard-id="${e}">Edit</button>
                <a class="secondary" href="/api/dashboards/${e}/export">Export JSON</a>
            </div>
        </div>
        <div class="dashboard-grid">${a||'<div class="dashboard-empty">No widgets configured.</div>'}</div>
    `,Zd(e,i,t)}function Qd(e,t){let n=Array.isArray(e?.layout?.widgets)?e.layout.widgets:[],r=Number.isFinite(e?.layout?.columns)?e.layout.columns:"",s=Number.isFinite(e?.refresh_interval)?e.refresh_interval:"";t.innerHTML=`
        <div class="dashboard-builder">
            <div class="dashboard-builder-header">
                <div>
                    <div class="dashboard-builder-title">Edit Dashboard</div>
                    <div class="dashboard-builder-subtitle">Update widgets, layout, and refresh settings.</div>
                </div>
                <div class="dashboard-builder-actions">
                    <button class="secondary" data-action="builder-cancel" data-dashboard-id="${e.id}">Cancel</button>
                    <button data-action="builder-save" data-dashboard-id="${e.id}">Save</button>
                </div>
            </div>

            <div class="dashboard-builder-form">
                <input type="text" id="dashboardEditName" value="${P(e.name||"")}" placeholder="Dashboard name" />
                <input type="text" id="dashboardEditDescription" value="${P(e.description||"")}" placeholder="Description (optional)" />
                <input type="number" id="dashboardEditRefresh" value="${s}" placeholder="Refresh interval (seconds)" min="1" />
                <input type="number" id="dashboardEditColumns" value="${r}" placeholder="Columns (1-6)" min="1" max="6" />
            </div>

            <div class="dashboard-builder-widgets" id="dashboardBuilderWidgets">
                ${n.map(o=>Si(o)).join("")}
            </div>

            <div class="dashboard-builder-footer">
                <button class="secondary" data-action="builder-add-widget" data-dashboard-id="${e.id}">Add Widget</button>
                <div class="dashboard-status" id="dashboardBuilderStatus"></div>
            </div>
        </div>
    `}function Si(e){let t=e?.query_id||"",n=e?.title||"",r=Number.isFinite(e?.limit)?e.limit:"",s=e?.sort_by||"",o=e?.id||"",i=Mr.map(a=>{let l=a.id===t?"selected":"";return`<option value="${a.id}" ${l}>${P(a.name)} \u2014 ${P(a.query)}</option>`}).join("");return`
        <div class="dashboard-builder-widget" data-widget-id="${P(o)}">
            <div class="dashboard-builder-widget-grid">
                <select class="dashboard-widget-query" aria-label="Saved query">
                    <option value="">Select saved query...</option>
                    ${i}
                </select>
                <input class="dashboard-widget-title" type="text" value="${P(n)}" placeholder="Widget title (optional)" />
                <input class="dashboard-widget-limit" type="number" value="${r}" min="1" max="100" placeholder="Limit" />
                <select class="dashboard-widget-sort" aria-label="Sort">
                    <option value="" ${s===""?"selected":""}>Sort (default)</option>
                    <option value="relevance" ${s==="relevance"?"selected":""}>Relevance</option>
                    <option value="date_newest" ${s==="date_newest"?"selected":""}>Newest</option>
                    <option value="date_oldest" ${s==="date_oldest"?"selected":""}>Oldest</option>
                    <option value="messages" ${s==="messages"?"selected":""}>Messages</option>
                </select>
            </div>
            <div class="dashboard-builder-widget-actions">
                <button class="secondary" data-action="builder-move-up">\u2191</button>
                <button class="secondary" data-action="builder-move-down">\u2193</button>
                <button class="secondary danger" data-action="builder-remove-widget">Remove</button>
            </div>
        </div>
    `}function Yd(e){let t=e.querySelector("#dashboardBuilderWidgets");if(!t)return;let n={id:`ui-${Date.now()}`,query_id:"",title:"",limit:5,sort_by:""};t.insertAdjacentHTML("beforeend",Si(n))}function Gd(e){let t=e.querySelector("#dashboardEditName")?.value?.trim()||"";if(!t)throw new Error("Dashboard name is required.");let n=e.querySelector("#dashboardEditDescription")?.value?.trim()||"",r=e.querySelector("#dashboardEditRefresh")?.value?.trim()||"",s=e.querySelector("#dashboardEditColumns")?.value?.trim()||"",o=r?Number.parseInt(r,10):null,i=s?Number.parseInt(s,10):null,l=Array.from(e.querySelectorAll(".dashboard-builder-widget")).map(u=>{let d=u.querySelector(".dashboard-widget-query")?.value?.trim()||"",f=u.querySelector(".dashboard-widget-title")?.value?.trim()||"",h=u.querySelector(".dashboard-widget-limit")?.value?.trim()||"",p=u.querySelector(".dashboard-widget-sort")?.value?.trim()||"";return{id:u.dataset.widgetId||""||null,query_id:d,title:f||null,limit:h?Number.parseInt(h,10):null,sort_by:p||null}});if(!l.length)throw new Error("At least one widget is required.");for(let u of l)if(!u.query_id)throw new Error("Each widget must select a saved query.");let c=[];for(let u of l)c.includes(u.query_id)||c.push(u.query_id);return{name:t,description:n||null,refresh_interval:Number.isFinite(o)?o:null,queries:c,layout:{widgets:l,columns:Number.isFinite(i)?i:null}}}function Zd(e,t,n){let r=Number.isFinite(t)?t:null;if(!r||r<=0){fn();return}un===e&&Hr===r&&Et||(fn(),un=e,Hr=r,Et=setInterval(async()=>{if(un===e)try{await xt(e,n)}catch{fn()}},r*1e3))}function dn(e,t,n){let r=Array.isArray(n)?n:[],s=Array.isArray(t)?t:[],o=r.length?r.map(a=>`
            <label class="dashboard-query-option">
                <input type="checkbox" value="${a.id}" />
                <span>${P(a.name)} <small>${P(a.query)}</small></span>
            </label>
        `).join(""):'<div class="dashboard-empty">No saved queries yet. Save a query to build widgets.</div>',i=s.length?s.map(a=>`
            <div class="dashboard-card" data-dashboard-id="${a.id}">
                <div>
                    <div class="dashboard-card-title">${P(a.name)}</div>
                    <div class="dashboard-card-meta">${P(a.description||"")}</div>
                </div>
                <div class="dashboard-card-actions">
                    <button data-action="view" data-dashboard-id="${a.id}">View</button>
                    <button data-action="edit" data-dashboard-id="${a.id}" class="secondary">Edit</button>
                    <button data-action="delete" data-dashboard-id="${a.id}" class="danger">Delete</button>
                </div>
            </div>
        `).join(""):'<div class="dashboard-empty">No dashboards yet.</div>';e.innerHTML=`
        <div class="dashboard-header">
            <div>
                <h2>Dashboards</h2>
                <p>Track saved queries as live widgets.</p>
            </div>
            <button class="link" data-action="back">\u2190 Back to Search</button>
        </div>

        <div class="dashboard-panel">
            <h3>Create Dashboard</h3>
            <div class="dashboard-form">
                <input type="text" id="dashboardName" placeholder="Dashboard name" />
                <input type="text" id="dashboardDescription" placeholder="Description (optional)" />
                <input type="number" id="dashboardRefresh" placeholder="Refresh interval (seconds)" min="1" />
            </div>
            <div class="dashboard-queries">
                ${o}
            </div>
            <div class="dashboard-form-actions">
                <button data-action="create">Create Dashboard</button>
            </div>
            <div class="dashboard-status" id="dashboardStatus"></div>
        </div>

        <div class="dashboard-panel">
            <h3>Saved Dashboards</h3>
            <div class="dashboard-list">${i}</div>
        </div>

        <div class="dashboard-panel" id="dashboardView"></div>
    `}function eu(){let e=document.querySelectorAll('.dashboard-queries input[type="checkbox"]'),t=[];return e.forEach(n=>{n.checked&&t.push(n.value)}),t}async function _i(){let e=document.getElementById("results");if(e){Ud(),e.innerHTML='<div class="dashboard-loading">Loading dashboards...</div>';try{if(!(await zd())?.dashboards?.enabled)e.innerHTML=`
                <div class="dashboard-panel">
                    <h2>Dashboards</h2>
                    <p>Dashboards are disabled. Enable <code>[dashboards].enabled = true</code> in <code>~/.searchat/config/settings.toml</code> to use this feature.</p>
                    <button class="link" data-action="back">\u2190 Back to Search</button>
                </div>
            `;else{let[n,r]=await Promise.all([ln(),cn()]);Mr=Array.isArray(r.queries)?r.queries:[],dn(e,n.dashboards,r.queries)}wi||(e.addEventListener("click",async n=>{let r=n.target;if(!(r instanceof HTMLElement))return;let s=r.dataset.action,o=r.dataset.dashboardId;if(s==="back"){fn(),Y(),await ie()||(sessionStorage.removeItem("lastView"),Y());return}if(s==="create"){let i=document.getElementById("dashboardStatus"),a=document.getElementById("dashboardName").value.trim();if(!a){i&&(i.textContent="Dashboard name is required.");return}let l=document.getElementById("dashboardDescription").value.trim(),c=document.getElementById("dashboardRefresh").value.trim(),u=c?Number.parseInt(c,10):null,d=eu();if(!d.length){i&&(i.textContent="Select at least one saved query.");return}let f=d.map(p=>({query_id:p})),h={name:a,description:l||null,refresh_interval:Number.isFinite(u)?u:null,queries:d,layout:{widgets:f}};try{await Jd(h);let[p,g]=await Promise.all([ln(),cn()]);dn(e,p.dashboards,g.queries)}catch(p){i&&(i.textContent=p.message)}}if(s==="view"&&o){let i=document.getElementById("dashboardView");if(!i)return;try{await xt(o,i)}catch(a){i.innerHTML=`<div class="dashboard-empty">${P(a.message)}</div>`}}if(s==="edit"&&o){let i=document.getElementById("dashboardView");if(!i)return;try{let l=(await Wd(o)).dashboard;if(!l)throw new Error("Dashboard not found");Qd(l,i)}catch(a){i.innerHTML=`<div class="dashboard-empty">${P(a.message)}</div>`}}if(s==="refresh"&&o){let i=document.getElementById("dashboardView");if(!i)return;try{await xt(o,i)}catch(a){i.innerHTML=`<div class="dashboard-empty">${P(a.message)}</div>`}}if(s==="delete"&&o){if(!window.confirm("Delete this dashboard?"))return;try{await Xd(o);let[a,l]=await Promise.all([ln(),cn()]);dn(e,a.dashboards,l.queries)}catch(a){let l=document.getElementById("dashboardStatus");l&&(l.textContent=a.message)}}if(s==="builder-add-widget"&&o){let i=document.getElementById("dashboardView");if(!i)return;Yd(i)}if(s==="builder-remove-widget"){let i=r.closest(".dashboard-builder-widget");i&&i.remove()}if(s==="builder-move-up"||s==="builder-move-down"){let i=r.closest(".dashboard-builder-widget");if(!i)return;s==="builder-move-up"&&i.previousElementSibling&&i.parentNode.insertBefore(i,i.previousElementSibling),s==="builder-move-down"&&i.nextElementSibling&&i.parentNode.insertBefore(i.nextElementSibling,i)}if(s==="builder-cancel"&&o){let i=document.getElementById("dashboardView");if(!i)return;try{await xt(o,i)}catch(a){i.innerHTML=`<div class="dashboard-empty">${P(a.message)}</div>`}}if(s==="builder-save"&&o){let i=document.getElementById("dashboardView");if(!i)return;let a=i.querySelector("#dashboardBuilderStatus");a&&(a.textContent="");try{let l=Gd(i);await Kd(o,l);let[c,u]=await Promise.all([ln(),cn()]);Mr=Array.isArray(u.queries)?u.queries:[],dn(e,c.dashboards,u.queries);let d=document.getElementById("dashboardView");d&&await xt(o,d)}catch(l){a&&(a.textContent=l.message)}}if(r.classList.contains("dashboard-result-open")){n.preventDefault();let i=r.dataset.conversationId;i&&await Ee(i)}}),wi=!0)}catch(t){e.innerHTML=`<div class="dashboard-empty">Failed to load dashboards: ${P(t.message)}</div>`}}}var wi,Et,un,Hr,Mr,Ci=M(()=>{we();Ge();wi=!1,Et=null,un=null,Hr=null,Mr=[]});function $(e){let t=document.createElement("div");return t.textContent=e||"",t.innerHTML}function tu(){let e=document.getElementById("filters"),t=document.querySelector(".toolbar"),n=[document.getElementById("heroTitle"),document.getElementById("heroSubtitle")];e&&(e.style.display="none"),t&&(t.style.display="none"),n.forEach(r=>{r&&(r.style.display="none")}),sessionStorage.setItem("lastView","expertise")}function nu(){let e=document.getElementById("filters"),t=document.querySelector(".toolbar");e&&(e.style.display=""),t&&(t.style.display="")}async function wt(e){let t=await fetch(e);if(!t.ok){let n=await t.json().catch(()=>null);throw new Error(n?.detail||`Request failed: ${t.status}`)}return t.json()}async function ru(){return wt("/api/expertise/status")}async function su(){return wt("/api/expertise/domains")}async function ou(e,t=0,n=tt){let r=new URLSearchParams;return e.domain&&r.set("domain",e.domain),e.type&&r.set("type",e.type),e.project&&r.set("project",e.project),e.tags&&r.set("tags",e.tags),e.severity&&r.set("severity",e.severity),e.q&&r.set("q",e.q),r.set("active_only",String(e.active_only)),r.set("limit",String(n)),r.set("offset",String(t)),wt(`/api/expertise?${r.toString()}`)}async function iu(e){return wt(`/api/expertise/${encodeURIComponent(e)}`)}async function au(e){return wt(`/api/knowledge-graph/lineage/${encodeURIComponent(e)}`)}function lu(e){return`<span class="health-badge health-badge--${e==="healthy"?"healthy":e==="critical"?"critical":"warning"}">${$(e)}</span>`}function cu(e){let t=Array.isArray(e.domains)?e.domains:[];return t.length?`
        <div class="expertise-table-wrap">
            <table class="expertise-table">
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Records</th>
                        <th>Active</th>
                        <th>Stale</th>
                        <th>Contradictions</th>
                        <th>Health</th>
                    </tr>
                </thead>
                <tbody>${t.map(r=>`
        <tr data-domain="${$(r.name)}">
            <td>${$(r.name)}</td>
            <td>${r.record_count??0}</td>
            <td>${r.active_count??0}</td>
            <td>${r.stale_count??0}</td>
            <td>${r.contradiction_count??0}</td>
            <td>${lu(r.health||"healthy")}</td>
        </tr>
    `).join("")}</tbody>
            </table>
        </div>
    `:'<div class="expertise-empty">No domains found.</div>'}function du(e){return`
        <div class="expertise-stats-row">
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Total Records</span>
                <span class="expertise-stat-value">${e.total_records??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Active</span>
                <span class="expertise-stat-value">${e.active_records??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Domains</span>
                <span class="expertise-stat-value">${(e.domains||[]).length}</span>
            </div>
        </div>
    `}function uu(e){let t=e.map(n=>`<option value="${$(n.name)}">${$(n.name)}</option>`).join("");return`
        <div class="expertise-filter-bar" id="expertiseFilterBar">
            <input type="text" id="expertiseSearch" placeholder="Search records..." value="${$(R.filters.q)}" />
            <select id="expertiseTypeFilter">
                <option value="">All Types</option>
                <option value="convention">Convention</option>
                <option value="pattern">Pattern</option>
                <option value="failure">Failure</option>
                <option value="decision">Decision</option>
                <option value="boundary">Boundary</option>
                <option value="insight">Insight</option>
            </select>
            <select id="expertiseDomainFilter">
                <option value="">All Domains</option>
                ${t}
            </select>
            <select id="expertiseSeverityFilter">
                <option value="">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
            </select>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:hsl(var(--text-tertiary));">
                <input type="checkbox" id="expertiseActiveOnly" ${R.filters.active_only?"checked":""} />
                Active only
            </label>
            <button class="glass-btn" id="expertiseApplyFilters">Apply</button>
        </div>
    `}function fu(e,t){return e.length?`
        <div class="expertise-record-list">${e.map(r=>{let s=(r.tags||[]).map(i=>`<span class="expertise-tag">${$(i)}</span>`).join(""),o=r.confidence!=null?`${Math.round(r.confidence*100)}%`:"";return`
            <div class="expertise-record-item" data-record-id="${$(r.id)}">
                <div class="expertise-record-main">
                    <div class="expertise-record-title">${$(r.name||r.content.slice(0,80))}</div>
                    <div class="expertise-record-meta">
                        <span>${$(r.type)}</span>
                        <span>${$(r.domain)}</span>
                        ${r.project?`<span>${$(r.project)}</span>`:""}
                        ${r.severity?`<span>${$(r.severity)}</span>`:""}
                    </div>
                    ${s?`<div class="expertise-record-tags">${s}</div>`:""}
                </div>
                <div class="expertise-record-confidence">${o}</div>
            </div>
        `}).join("")}</div>
    `:'<div class="expertise-empty">No records match the current filters.</div>'}function pu(e,t){let n=Math.max(1,Math.ceil(e/tt));if(n<=1)return"";let r=t*tt+1,s=Math.min((t+1)*tt,e);return`
        <div class="expertise-pagination">
            <button class="glass-btn" id="expertisePrevPage" ${t===0?"disabled":""}>Prev</button>
            <span class="expertise-pagination-info">${r}\u2013${s} of ${e}</span>
            <button class="glass-btn" id="expertiseNextPage" ${t>=n-1?"disabled":""}>Next</button>
        </div>
    `}function hu(e,t){let n=(e.tags||[]).map(o=>`<span class="expertise-tag">${$(o)}</span>`).join(""),r=(t?.conversations||[]).map(o=>`<li><a href="/conversation/${encodeURIComponent(o)}">${$(o)}</a></li>`).join(""),s=(t?.derived_records||[]).map(o=>`<li>${$(o)}</li>`).join("");return`
        <div class="expertise-detail-panel" id="expertiseDetailPanel">
            <div class="expertise-detail-header">
                <h3>${$(e.name||e.type)}</h3>
                <button class="expertise-detail-close" id="expertiseDetailClose" aria-label="Close">&#x2715;</button>
            </div>
            <div class="expertise-detail-meta-grid">
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Type</span>
                    <span class="expertise-detail-field-value">${$(e.type)}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Domain</span>
                    <span class="expertise-detail-field-value">${$(e.domain)}</span>
                </div>
                ${e.project?`
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Project</span>
                    <span class="expertise-detail-field-value">${$(e.project)}</span>
                </div>`:""}
                ${e.severity?`
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Severity</span>
                    <span class="expertise-detail-field-value">${$(e.severity)}</span>
                </div>`:""}
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Confidence</span>
                    <span class="expertise-detail-field-value">${e.confidence!=null?Math.round(e.confidence*100)+"%":"\u2014"}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Validations</span>
                    <span class="expertise-detail-field-value">${e.validation_count??0}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Status</span>
                    <span class="expertise-detail-field-value">${e.is_active?"Active":"Inactive"}</span>
                </div>
                <div class="expertise-detail-field">
                    <span class="expertise-detail-field-label">Created</span>
                    <span class="expertise-detail-field-value">${e.created_at?new Date(e.created_at).toLocaleDateString():"\u2014"}</span>
                </div>
            </div>
            <div class="expertise-detail-content">${$(e.content)}</div>
            ${e.example?`<div class="expertise-detail-field"><span class="expertise-detail-field-label">Example</span><div class="expertise-detail-content" style="margin-top:4px;">${$(e.example)}</div></div>`:""}
            ${e.rationale?`<div class="expertise-detail-field"><span class="expertise-detail-field-label">Rationale</span><div class="expertise-detail-content" style="margin-top:4px;">${$(e.rationale)}</div></div>`:""}
            ${n?`<div class="expertise-record-tags">${n}</div>`:""}
            ${e.source_conversation_id?`
                <div class="expertise-detail-provenance">
                    <span>Source:</span>
                    <a href="/conversation/${encodeURIComponent(e.source_conversation_id)}">${$(e.source_conversation_id)}</a>
                    ${e.source_agent?`<span>via ${$(e.source_agent)}</span>`:""}
                </div>`:""}
            ${r||s?`
                <div class="expertise-detail-lineage">
                    <h4>Lineage</h4>
                    ${r?`
                        <p style="font-size:11px;color:hsl(var(--text-tertiary));margin:0 0 6px;">Source Conversations</p>
                        <ul class="expertise-lineage-list">${r}</ul>`:""}
                    ${s?`
                        <p style="font-size:11px;color:hsl(var(--text-tertiary));margin:8px 0 6px;">Derived Records</p>
                        <ul class="expertise-lineage-list">${s}</ul>`:""}
                </div>`:""}
        </div>
    `}function Rr(e){e.querySelector(".expertise-inline-detail")?.remove()}function mu(e,t){Rr(e);let n=document.createElement("div");return n.className="expertise-inline-detail",t.insertAdjacentElement("afterend",n),n}async function gu(e){e.innerHTML='<div class="expertise-loading">Loading domain status...</div>';try{let t=await ru();e.innerHTML=du(t)+cu(t),e.querySelectorAll(".expertise-table tbody tr").forEach(n=>{n.addEventListener("click",()=>{R.filters.domain=n.dataset.domain||"",R.page=0,Dr(document.getElementById("results"),"records")})})}catch(t){e.innerHTML=`<div class="expertise-error">${$(t.message)}</div>`}}async function pn(e){e.innerHTML='<div class="expertise-loading">Loading records...</div>';try{let[t,n]=await Promise.all([su(),ou(R.filters,R.page*tt)]),r=uu(t),s=fu(n.results,n.total),o=pu(n.total,R.page);e.innerHTML=r+s+o;let i=e.querySelector("#expertiseDomainFilter");i&&(i.value=R.filters.domain);let a=e.querySelector("#expertiseTypeFilter");a&&(a.value=R.filters.type);let l=e.querySelector("#expertiseSeverityFilter");l&&(l.value=R.filters.severity);let c=e.querySelector("#expertiseApplyFilters");c&&c.addEventListener("click",()=>{R.filters.q=e.querySelector("#expertiseSearch")?.value?.trim()||"",R.filters.type=e.querySelector("#expertiseTypeFilter")?.value||"",R.filters.domain=e.querySelector("#expertiseDomainFilter")?.value||"",R.filters.severity=e.querySelector("#expertiseSeverityFilter")?.value||"",R.filters.active_only=e.querySelector("#expertiseActiveOnly")?.checked??!0,R.page=0,pn(e)});let u=e.querySelector("#expertiseSearch");u&&u.addEventListener("keypress",d=>{d.key==="Enter"&&c?.click()}),e.querySelectorAll(".expertise-record-item").forEach(d=>{d.addEventListener("click",async()=>{let f=d.dataset.recordId;if(!f)return;if(R.selectedRecordId===f){R.selectedRecordId=null,d.classList.remove("selected"),Rr(e);return}R.selectedRecordId=f,e.querySelectorAll(".expertise-record-item").forEach(p=>p.classList.remove("selected")),d.classList.add("selected");let h=mu(e,d);h.innerHTML='<div class="expertise-loading">Loading record...</div>';try{let[p,g]=await Promise.all([iu(f),au(f).catch(()=>null)]);h.innerHTML=hu(p,g),h.querySelector("#expertiseDetailClose")?.addEventListener("click",()=>{Rr(e),h.innerHTML="",R.selectedRecordId=null,d.classList.remove("selected")}),d.scrollIntoView({behavior:"smooth",block:"nearest"})}catch(p){h.innerHTML=`<div class="expertise-error">${$(p.message)}</div>`}})}),e.querySelector("#expertisePrevPage")?.addEventListener("click",()=>{R.page>0&&(R.page--,pn(e))}),e.querySelector("#expertiseNextPage")?.addEventListener("click",()=>{let d=Math.ceil(n.total/tt);R.page<d-1&&(R.page++,pn(e))})}catch(t){e.innerHTML=`<div class="expertise-error">${$(t.message)}</div>`}}function Dr(e,t){R.activeTab=t,e.querySelectorAll(".expertise-tab-btn").forEach(r=>{r.classList.toggle("active",r.dataset.tab===t)}),e.querySelectorAll(".expertise-tab-panel").forEach(r=>{r.classList.toggle("active",r.dataset.panel===t)});let n=e.querySelector(`.expertise-tab-panel[data-panel="${t}"]`);n&&(t==="domains"?gu(n):t==="records"&&pn(n))}async function Or(){let e=document.getElementById("results");if(!e)return;tu(),e.innerHTML=`
        <div class="expertise-view">
            <div class="expertise-header">
                <div>
                    <h2>Expertise</h2>
                    <p>Browse and manage extracted knowledge records.</p>
                </div>
                <div class="expertise-header-actions">
                    <button class="glass-btn" data-action="back" id="expertiseBackBtn">&#x2190; Back to Search</button>
                </div>
            </div>
            <div class="expertise-tabs">
                <button class="expertise-tab-btn active" data-tab="domains">Domain Health</button>
                <button class="expertise-tab-btn" data-tab="records">Records</button>
            </div>
            <div class="expertise-tab-panel active" data-panel="domains"></div>
            <div class="expertise-tab-panel" data-panel="records"></div>
        </div>
    `,e.querySelectorAll(".expertise-tab-btn").forEach(n=>{n.addEventListener("click",()=>Dr(e,n.dataset.tab))}),e.querySelector("#expertiseBackBtn")?.addEventListener("click",async()=>{nu(),Y(),await ie()||(sessionStorage.removeItem("lastView"),Y())});let t=R.activeTab||"domains";Dr(e,t)}var tt,R,ki=M(()=>{we();Ge();tt=25,R={page:0,filters:{type:"",domain:"",project:"",tags:"",severity:"",active_only:!0,q:""},selectedRecordId:null,activeTab:"domains"}});function K(e){let t=document.createElement("div");return t.textContent=e||"",t.innerHTML}function vu(){let e=document.getElementById("filters"),t=document.querySelector(".toolbar"),n=[document.getElementById("heroTitle"),document.getElementById("heroSubtitle")];e&&(e.style.display="none"),t&&(t.style.display="none"),n.forEach(r=>{r&&(r.style.display="none")}),sessionStorage.setItem("lastView","contradictions")}function yu(){let e=document.getElementById("filters"),t=document.querySelector(".toolbar");e&&(e.style.display=""),t&&(t.style.display="")}async function Pr(e){let t=await fetch(e);if(!t.ok){let n=await t.json().catch(()=>null);throw new Error(n?.detail||`Request failed: ${t.status}`)}return t.json()}async function bu(e,t){let n=await fetch(e,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(t)});if(!n.ok){let r=await n.json().catch(()=>null);throw new Error(r?.detail||`Request failed: ${n.status}`)}return n.json()}async function xu(e=!0){let t=new URLSearchParams({unresolved_only:String(e)});return Pr(`/api/knowledge-graph/contradictions?${t.toString()}`)}async function Ii(e){return Pr(`/api/expertise/${encodeURIComponent(e)}`)}async function Eu(){return Pr("/api/knowledge-graph/stats")}async function _t(e,t,n){return bu("/api/knowledge-graph/resolve",{edge_id:e,strategy:t,params:n})}function wu(e){let t=Math.round((e.health_score??0)*100),n=t>=80?"var(--success)":t>=50?"var(--warning)":"var(--danger)";return`
        <div class="kg-stats-row">
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Nodes</span>
                <span class="expertise-stat-value">${e.node_count??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Edges</span>
                <span class="expertise-stat-value">${e.edge_count??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Contradictions</span>
                <span class="expertise-stat-value" style="color:hsl(var(--danger))">${e.contradiction_count??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Unresolved</span>
                <span class="expertise-stat-value" style="color:hsl(var(--warning))">${e.unresolved_contradiction_count??0}</span>
            </div>
            <div class="expertise-stat-card">
                <span class="expertise-stat-label">Health</span>
                <span class="expertise-stat-value" style="color:hsl(${n})">${t}%</span>
                <div class="kg-health-bar">
                    <div class="kg-health-bar-fill" style="width:${t}%;background:hsl(${n})"></div>
                </div>
            </div>
        </div>
    `}function Su(e){return e.length?`<div class="contradiction-list">${e.map(n=>`
        <div class="contradiction-item" data-edge-id="${K(n.edge_id)}" data-record-a="${K(n.record_id_a)}" data-record-b="${K(n.record_id_b)}">
            <div>
                <div class="contradiction-item-ids">${K(n.record_id_a.slice(0,8))} &#x21C4; ${K(n.record_id_b.slice(0,8))}</div>
                <div class="contradiction-item-meta">${new Date(n.created_at).toLocaleDateString()}</div>
            </div>
            <button class="glass-btn" style="font-size:11px;padding:4px 10px;" data-resolve-edge="${K(n.edge_id)}">Resolve</button>
        </div>
    `).join("")}</div>`:`
            <div class="contradiction-all-resolved">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                All contradictions resolved.
            </div>
        `}function Ti(e,t,n=!1){return`
        <div class="contradiction-record-card ${n?"winner":""}" data-record-card="${K(e.id)}">
            <h4>${K(t)}: ${K(e.id.slice(0,8))}</h4>
            <div class="contradiction-record-content">${K(e.content)}</div>
            <div class="contradiction-record-meta">
                <span><strong>Type:</strong> ${K(e.type)}</span>
                <span><strong>Domain:</strong> ${K(e.domain)}</span>
                ${e.project?`<span><strong>Project:</strong> ${K(e.project)}</span>`:""}
                <span><strong>Confidence:</strong> ${e.confidence!=null?Math.round(e.confidence*100)+"%":"\u2014"}</span>
            </div>
        </div>
    `}function _u(e,t,n){return`
        <div class="contradiction-actions" id="contradictionActions">
            <h4>Resolve Contradiction</h4>
            <div class="contradiction-action-row" id="contradictionActionButtons">
                <button class="glass-btn" data-strategy="supersede" data-winner="${K(t.id)}">A Supersedes B</button>
                <button class="glass-btn" data-strategy="supersede" data-winner="${K(n.id)}">B Supersedes A</button>
                <button class="glass-btn" data-strategy="scope_both">Scope Both</button>
                <button class="glass-btn" data-strategy="merge">Merge</button>
                <button class="glass-btn" data-strategy="dismiss">Dismiss</button>
                <button class="glass-btn" data-strategy="keep_both">Keep Both</button>
            </div>

            <div class="contradiction-scope-input" id="contradictionScopeInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Scope for Record A</label>
                <input type="text" id="scopeA" placeholder="e.g. applies only to production" />
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Scope for Record B</label>
                <input type="text" id="scopeB" placeholder="e.g. applies only to staging" />
                <button class="glass-btn glass-btn-primary" id="confirmScope">Confirm Scope</button>
            </div>

            <div class="contradiction-merge-input" id="contradictionMergeInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Merged content</label>
                <textarea id="mergedContent" rows="3" placeholder="Enter merged knowledge content..."></textarea>
                <button class="glass-btn glass-btn-primary" id="confirmMerge">Confirm Merge</button>
            </div>

            <div class="contradiction-dismiss-input" id="contradictionDismissInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Reason for dismissal</label>
                <input type="text" id="dismissReason" placeholder="e.g. false positive, context mismatch" />
                <button class="glass-btn glass-btn-primary" id="confirmDismiss">Confirm Dismiss</button>
            </div>

            <div class="contradiction-dismiss-input" id="contradictionKeepBothInput">
                <label style="font-size:11px;color:hsl(var(--text-tertiary));">Reason to keep both</label>
                <input type="text" id="keepBothReason" placeholder="e.g. different contexts, both valid" />
                <button class="glass-btn glass-btn-primary" id="confirmKeepBoth">Confirm Keep Both</button>
            </div>

            <div class="contradiction-status" id="contradictionStatus"></div>
        </div>
    `}function $i(e){e.querySelector(".contradiction-inline-detail")?.remove()}function Cu(e,t){$i(e);let n=document.createElement("div");return n.className="contradiction-inline-detail",t.insertAdjacentElement("afterend",n),n}function ku(e,t,n,r,s){let o=e.querySelector("#contradictionStatus"),i=e.querySelector("#contradictionScopeInput"),a=e.querySelector("#contradictionMergeInput"),l=e.querySelector("#contradictionDismissInput"),c=e.querySelector("#contradictionKeepBothInput");function u(){[i,a,l,c].forEach(d=>{d&&d.classList.remove("visible")})}e.querySelectorAll("[data-strategy]").forEach(d=>{d.addEventListener("click",async()=>{let f=d.dataset.strategy;if(u(),o.textContent="",o.className="contradiction-status",f==="supersede"){let h=d.dataset.winner;try{await _t(t,"supersede",{winner_id:h}),o.textContent="Resolved: supersede applied.",o.classList.add("success"),s()}catch(p){o.textContent=p.message,o.classList.add("error")}}else f==="scope_both"?i.classList.add("visible"):f==="merge"?a.classList.add("visible"):f==="dismiss"?l.classList.add("visible"):f==="keep_both"&&c.classList.add("visible")})}),e.querySelector("#confirmScope")?.addEventListener("click",async()=>{let d=e.querySelector("#scopeA")?.value?.trim(),f=e.querySelector("#scopeB")?.value?.trim();if(!d||!f){o.textContent="Both scope fields required.",o.classList.add("error");return}try{await _t(t,"scope_both",{scope_a:d,scope_b:f}),o.textContent="Resolved: scopes applied.",o.classList.add("success"),s()}catch(h){o.textContent=h.message,o.classList.add("error")}}),e.querySelector("#confirmMerge")?.addEventListener("click",async()=>{let d=e.querySelector("#mergedContent")?.value?.trim();if(!d){o.textContent="Merged content required.",o.classList.add("error");return}try{await _t(t,"merge",{merged_content:d}),o.textContent="Resolved: records merged.",o.classList.add("success"),s()}catch(f){o.textContent=f.message,o.classList.add("error")}}),e.querySelector("#confirmDismiss")?.addEventListener("click",async()=>{let d=e.querySelector("#dismissReason")?.value?.trim();if(!d){o.textContent="Dismiss reason required.",o.classList.add("error");return}try{await _t(t,"dismiss",{reason:d}),o.textContent="Resolved: contradiction dismissed.",o.classList.add("success"),s()}catch(f){o.textContent=f.message,o.classList.add("error")}}),e.querySelector("#confirmKeepBoth")?.addEventListener("click",async()=>{let d=e.querySelector("#keepBothReason")?.value?.trim();if(!d){o.textContent="Reason required.",o.classList.add("error");return}try{await _t(t,"keep_both",{reason:d}),o.textContent="Resolved: both records kept.",o.classList.add("success"),s()}catch(f){o.textContent=f.message,o.classList.add("error")}})}async function jr(e,t=!0){e.innerHTML='<div class="expertise-loading">Loading contradictions...</div>';try{let[n,r]=await Promise.all([Eu(),xu(t)]),s=wu(n),o=Su(r.results||[]);e.innerHTML=`
            ${s}
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
                <h3 style="margin:0;font-size:15px;font-weight:600;">
                    ${t?"Unresolved":"All"} Contradictions
                    <span style="font-size:12px;font-weight:400;color:hsl(var(--text-tertiary));margin-left:8px;">${r.total??0} found</span>
                </h3>
                <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:hsl(var(--text-tertiary));">
                    <input type="checkbox" id="contradictionUnresolvedOnly" ${t?"checked":""} />
                    Unresolved only
                </label>
            </div>
            ${o}
        `,e.querySelector("#contradictionUnresolvedOnly")?.addEventListener("change",i=>{jr(e,i.target.checked)}),e.querySelectorAll(".contradiction-item").forEach(i=>{i.addEventListener("click",async a=>{a.target.dataset.resolveEdge||a.target.closest("[data-resolve-edge]")||Ai(e,i)})}),e.querySelectorAll("[data-resolve-edge]").forEach(i=>{i.addEventListener("click",async()=>{let a=i.closest(".contradiction-item");a&&Ai(e,a)})})}catch(n){e.innerHTML=`<div class="expertise-error">${K(n.message)}</div>`}}async function Ai(e,t){let n=t.dataset.edgeId,r=t.dataset.recordA,s=t.dataset.recordB;if(!n)return;if(St.selectedEdgeId===n){St.selectedEdgeId=null,t.classList.remove("selected"),$i(e);return}e.querySelectorAll(".contradiction-item").forEach(i=>i.classList.remove("selected")),t.classList.add("selected");let o=Cu(e,t);o.innerHTML='<div class="expertise-loading">Loading records...</div>';try{let[i,a]=await Promise.all([Ii(r),Ii(s)]);St.recordA=i,St.recordB=a,St.selectedEdgeId=n,o.innerHTML=`
            <div style="margin-top:16px;">
                <div class="contradiction-comparison">
                    ${Ti(i,"Record A")}
                    ${Ti(a,"Record B")}
                </div>
                <div style="margin-top:12px;">
                    ${_u(n,i,a)}
                </div>
            </div>
        `;let l=e.querySelector("#contradictionUnresolvedOnly")?.checked??!0;ku(o,n,i,a,()=>{setTimeout(()=>jr(e,l),800)}),t.scrollIntoView({behavior:"smooth",block:"nearest"})}catch(i){o.innerHTML=`<div class="expertise-error">${K(i.message)}</div>`}}async function qr(){let e=document.getElementById("results");if(!e)return;vu(),e.innerHTML=`
        <div class="expertise-view">
            <div class="expertise-header">
                <div>
                    <h2>Knowledge Graph</h2>
                    <p>Detect and resolve contradictions between expertise records.</p>
                </div>
                <div class="expertise-header-actions">
                    <button class="glass-btn" id="contradictionsBackBtn">&#x2190; Back to Search</button>
                </div>
            </div>
            <div id="contradictionsBody"></div>
        </div>
    `,e.querySelector("#contradictionsBackBtn")?.addEventListener("click",async()=>{yu(),Y(),await ie()||(sessionStorage.removeItem("lastView"),Y())});let t=e.querySelector("#contradictionsBody");t&&await jr(t,!0)}var St,Li=M(()=>{we();Ge();St={selectedEdgeId:null,recordA:null,recordB:null,pendingStrategy:null}});function F(e){let t=document.createElement("div");return t.textContent=e==null?"":String(e),t.innerHTML}function Iu(e){if(!e)return"";try{return new Date(e).toLocaleDateString()}catch{return String(e).slice(0,10)}}function Tu(e){if(e.tool)return e.tool;let t=String(e.file_path||"").toLowerCase();return t.includes("vibe")?"vibe":t.includes("claude")?"claude":t.includes("codex")?"codex":t.includes("gemini")?"gemini":t.includes("cursor")?"cursor":""}function Au(){let e=new Set,t=document.getElementById("confirmOverlay"),n=document.getElementById("confirmMessage"),r=document.getElementById("confirmOk"),s=document.getElementById("confirmCancel"),o=document.getElementById("manage-list"),i=document.getElementById("manageToolbar"),a=document.getElementById("manageSelectionCount"),l=document.getElementById("previewPanel"),c=document.getElementById("previewOverlay"),u=document.getElementById("previewContent"),d=document.getElementById("manageDeleteBtn"),f=document.getElementById("deleteSourceFiles"),h={state:{page:1,pageSize:50,totalPages:0}};function p(){!i||!a||(e.size>0?(i.style.display="flex",a.textContent=`${e.size} selected`):i.style.display="none")}function g(){!l||!c||(l.classList.add("open"),c.classList.add("open"),document.body.style.overflow="hidden")}function m(){!l||!c||(l.classList.remove("open"),c.classList.remove("open"),document.body.style.overflow="")}function v(E){if(!E||typeof E!="object")return'<div class="preview-error"><p>Conversation not found.</p></div>';let S=Array.isArray(E.messages)?E.messages:[],_=S.slice(0,10),C=Math.max(S.length-_.length,0),w=Tu(E),k='<div class="preview-header">';return k+=`<h3 class="preview-title">${F(E.title||"Untitled Conversation")}</h3>`,k+='<div class="preview-meta">',E.project_id&&(k+=`<span>${F(E.project_id)}</span>`),E.message_count&&(k+=`<span>${F(E.message_count)} messages</span>`),E.created_at&&(k+=`<span>${F(String(E.created_at).slice(0,10))}</span>`),w&&(k+=`<span class="manage-tool-badge manage-tool-${F(w)}">${F(w)}</span>`),k+="</div></div>",k+='<div class="preview-messages">',_.forEach(L=>{let z=F(L&&L.role||"unknown"),D=F(L&&L.content||"");k+=`<div class="preview-message preview-role-${z}">`,k+=`<div class="preview-message-role">${z}</div>`,k+=`<div class="preview-message-content">${D}</div>`,k+="</div>"}),C>0&&(k+=`<div class="preview-truncated">&hellip; ${C} more message${C!==1?"s":""} not shown</div>`),k+="</div>",k}function y(E){if(!o)return;let S=Array.isArray(E.results)?E.results:[],_=Number(E.total||0);if(h.state.totalPages=_>0?Math.ceil(_/h.state.pageSize):0,!S.length){o.innerHTML='<div class="result" style="padding: 48px; text-align: center;"><p style="color: hsl(var(--text-tertiary)); margin: 0;">No conversations found.</p></div>',p();return}let C=`<div class="results-header">${_} conversation${_!==1?"s":""}`;h.state.page>1&&(C+=` &middot; Page ${h.state.page} of ${h.state.totalPages}`),C+="</div>",S.forEach(w=>{let k=e.has(w.conversation_id)?" checked":"",L=String(w.file_path||"");C+=`
<div class="result manage-result" id="manage-${F(w.conversation_id)}">
    <label class="manage-checkbox">
        <input type="checkbox" name="cid" value="${F(w.conversation_id)}"${k}>
        <span class="manage-checkmark"></span>
    </label>
    <div class="manage-result-content">
        <div class="result-title">${F(w.title||"Untitled")}</div>
        <div class="result-meta">
            <span>${F(w.project_id||"")}</span>
            ${w.message_count?`<span>&middot; ${F(w.message_count)} messages</span>`:""}
            ${w.updated_at?`<span>&middot; ${F(Iu(w.updated_at))}</span>`:""}
            ${w.tool?`<span class="manage-tool-badge manage-tool-${F(w.tool)}">${F(w.tool)}</span>`:""}
        </div>
        ${L?`<div class="manage-source-path" title="${F(L)}">${F(L)}</div>`:""}
    </div>
    <button class="glass-btn manage-preview-btn" title="Preview conversation" data-conversation-id="${F(w.conversation_id)}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
    </button>
</div>`}),h.state.totalPages>1&&(C+='<div class="manage-pagination">',h.state.page>1&&(C+='<button class="glass-btn" data-manage-page="prev">&larr; Previous</button>'),C+=`<span class="manage-page-info">Page ${h.state.page} of ${h.state.totalPages}</span>`,h.state.page<h.state.totalPages&&(C+='<button class="glass-btn" data-manage-page="next">Next &rarr;</button>'),C+="</div>"),o.innerHTML=C,p()}function x(){if(!o)return Promise.resolve();o.innerHTML='<div style="text-align: center; padding: 48px;"><span class="spinner" id="manageSpinner" style="display: inline-block;"></span><p style="color: hsl(var(--text-tertiary));">Loading conversations...</p></div>';let E=new URLSearchParams({sort_by:document.getElementById("manageSortBy").value,limit:String(h.state.pageSize),offset:String((h.state.page-1)*h.state.pageSize)}),S=document.getElementById("manageProject").value,_=document.getElementById("manageTool").value;return S&&E.set("project",S),_&&E.set("tool",_),fetch(`/api/conversations/all?${E.toString()}`).then(C=>{if(!C.ok)throw new Error("Failed to load conversations");return C.json()}).then(C=>{y(C)}).catch(C=>{o.innerHTML=`<div class="result" style="padding: 48px; text-align: center;"><p style="color: hsl(var(--danger)); margin: 0;">${F(C.message)}</p></div>`})}function b(){let E=document.getElementById("manageProject");return E?fetch("/api/projects/summary").then(S=>S.ok?S.json():[]).then(S=>{if(!Array.isArray(S))return;let _=E.value;E.innerHTML='<option value="">All Projects</option>',S.forEach(C=>{let w=document.createElement("option");w.value=C.project_id,w.textContent=`${C.project_id} (${C.conversation_count})`,E.appendChild(w)}),_&&(E.value=_)}).catch(()=>null):Promise.resolve()}function j(E,S){d&&(d.disabled=!0,d.textContent="Deleting...",fetch("/api/conversations/delete",{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_ids:E,delete_source_files:S})}).then(_=>{if(!_.ok)throw new Error(`Delete failed: ${_.status}`);return _.json()}).then(_=>{e.clear(),p(),x();let C=document.createElement("div");C.className="manage-notification glass",C.innerHTML=`<strong>Deleted ${_.deleted} conversation${_.deleted>1?"s":""}.</strong> Removed ${_.removed_vectors} vectors.`+(_.source_files_deleted>0?` Deleted ${_.source_files_deleted} source file${_.source_files_deleted>1?"s":""}.`:""),document.querySelector(".manage-page").insertBefore(C,o),setTimeout(()=>C.remove(),8e3)}).catch(_=>{alert(`Delete failed: ${_.message}`)}).finally(()=>{d.disabled=!1,d.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Delete Selected'}))}function V(){if(!t||!n||!r||!s||e.size===0)return;let E=!!(f&&f.checked),S=e.size,C=`Remove ${`${S} conversation${S>1?"s":""}`} from the search index?`;E&&(C+=`

The original source files (e.g. ~/.claude/projects/.../*.jsonl) will also be permanently deleted from disk.`),n.textContent=C,t.classList.add("active"),t.setAttribute("aria-hidden","false");let w,k,L,z=()=>{r.removeEventListener("click",w),s.removeEventListener("click",k),document.removeEventListener("keydown",L),t.classList.remove("active"),t.setAttribute("aria-hidden","true")};w=()=>{z(),j(Array.from(e),E)},k=()=>z(),L=D=>{D.key==="Escape"&&z()},r.addEventListener("click",w),s.addEventListener("click",k),document.addEventListener("keydown",L)}function B(){o&&(o.addEventListener("change",E=>{if(!E.target.matches('.manage-checkbox input[type="checkbox"]'))return;let S=E.target.value;E.target.checked?e.add(S):e.delete(S),p()}),o.addEventListener("click",E=>{let S=E.target.closest(".manage-preview-btn");if(S){let C=S.dataset.conversationId;if(!C||!u)return;g(),u.innerHTML='<div style="text-align: center; padding: 48px;"><span class="spinner" id="previewSpinner" style="display: inline-block;"></span></div>',fetch(`/api/conversation/${encodeURIComponent(C)}`).then(w=>{if(!w.ok)throw new Error("Failed to load preview");return w.json()}).then(w=>{u.innerHTML=v(w)}).catch(w=>{u.innerHTML=`<div style="padding: 24px; color: hsl(var(--danger));">${F(w.message)}</div>`});return}let _=E.target.closest("[data-manage-page]");_&&(_.dataset.managePage==="prev"&&h.state.page>1?h.state.page-=1:_.dataset.managePage==="next"&&h.state.page<h.state.totalPages&&(h.state.page+=1),x())}))}function U(){["manageProject","manageTool","manageSortBy"].forEach(S=>{let _=document.getElementById(S);_&&_.addEventListener("change",()=>{h.state.page=1,x()})}),document.getElementById("manageSelectAllButton")?.addEventListener("click",()=>{document.querySelectorAll('#manage-list .manage-checkbox input[type="checkbox"]').forEach(S=>{S.checked=!0,e.add(S.value)}),p()}),document.getElementById("manageDeselectAllButton")?.addEventListener("click",()=>{document.querySelectorAll('#manage-list .manage-checkbox input[type="checkbox"]').forEach(S=>{S.checked=!1}),e.clear(),p()}),d?.addEventListener("click",V),c?.addEventListener("click",m),document.getElementById("previewCloseButton")?.addEventListener("click",m),document.addEventListener("keydown",S=>{S.key==="Escape"&&l?.classList.contains("open")&&m()})}return{init(){B(),U(),b().finally(x)}}}function Bi(){if(!document.getElementById("manage-list"))return;Au().init()}var Hi=M(()=>{});async function Mi(){if(confirm("Create a backup of your search index?"))try{let n=await(await fetch("/api/backup/create",{method:"POST"})).json();n.success?alert(`\u2713 Backup created successfully!

Backup: ${n.backup.backup_path.split(/[/\\]/).pop()}
Size: ${n.backup.total_size_mb} MB
Files: ${n.backup.file_count}`):alert("Failed to create backup")}catch(t){alert(`Error creating backup: ${t.message}`)}}async function Ri(){try{let t=await(await fetch("/api/backup/list")).json();if(t.backups.length===0){alert(`No backups found.

Create your first backup using the "Create Backup" button.`);return}let n=`Available Backups (${t.total}):

`;t.backups.forEach((r,s)=>{let o=r.backup_path.split(/[/\\]/).pop(),i=new Date(r.timestamp.replace(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/,"$1-$2-$3T$4:$5:$6"));n+=`${s+1}. ${o}
`,n+=`   ${i.toLocaleString()} - ${r.total_size_mb} MB (${r.file_count} files)

`}),n+=`
Backup Directory: ${t.backup_directory}

`,n+=`To restore or delete backups, use:
`,n+=`POST /api/backup/restore
`,n+="DELETE /api/backup/delete/{name}",alert(n)}catch(e){alert(`Error loading backups: ${e.message}`)}}var Di=M(()=>{});async function Pi(){let e=document.getElementById("results"),t=document.getElementById("filters"),n=[document.getElementById("heroTitle"),document.getElementById("heroSubtitle"),document.getElementById("search")];t.style.display="none",n.forEach(r=>{r&&(r.style.display="none")}),e.innerHTML='<div class="loading">Loading disk usage...</div>',await ji(e)}async function ji(e){try{let t=await fetch("/api/disk");if(!t.ok)throw new Error(`Request failed with status ${t.status}`);let n=await t.json();e.innerHTML=`
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; gap: 12px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">
                        <h2 style="margin: 0; font-size: 28px; color: hsl(var(--text-primary));">Disk Manager</h2>
                        <button id="diskRefresh" class="glass-btn">Refresh</button>
                    </div>
                    <a href="/" style="color: hsl(var(--accent)); text-decoration: none; font-weight: 500;">&#8592; Back to Search</a>
                </div>

                <!-- Agents -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Registered Agents</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Per-connector disk usage: size on disk, conversation count, age, and indexed-vs-unindexed delta. Read-only.</p>
                    ${$u(n.agents)}
                </div>

                <!-- Searchat self -->
                <div class="glass">
                    <div class="card-title">Searchat's Own Footprint</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Index, backups, models, and expertise storage under ${hn(n.searchat_self.search_dir)}.</p>
                    ${Bu(n.searchat_self)}
                </div>
            </div>
        `;let r=document.getElementById("diskRefresh");r&&r.addEventListener("click",async()=>{e.innerHTML='<div class="loading">Loading disk usage...</div>',await ji(e)})}catch(t){e.innerHTML=`
            <div style="text-align: center; padding: 40px; color: hsl(var(--danger));">
                Failed to load disk usage: ${hn(t.message)}
                <br><br>
                <a href="/" style="color: hsl(var(--accent));">&#8592; Back to Search</a>
            </div>
        `}}function $u(e){return!e||e.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No registered connectors discovered any files.</div>':`
        <div class="stat-grid" style="margin-bottom: 20px;">
            ${e.map(t=>Lu(t)).join("")}
        </div>
    `}function Lu(e){let t=e.unindexed_file_count>0?"bad":"good";return`
        <div class="stat-card" style="min-width: 220px;">
            <div class="stat-label">${hn(e.connector)}</div>
            <div class="stat-value neutral">${Nr(e.total_size_bytes)}</div>
            <div class="stat-sub">${e.total_file_count} files &middot; ${e.conversation_file_count} conversations</div>
            <div style="margin-top: 8px; font-size: 12px; color: hsl(var(--text-tertiary));">
                <span class="badge badge-good">${e.indexed_file_count} indexed</span>
                <span class="badge badge-${t==="bad"?"bad":"good"}" style="margin-left: 4px;">${e.unindexed_file_count} unindexed</span>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: hsl(var(--text-tertiary));">
                Age: ${Oi(e.newest_conversation_age_days)} &ndash; ${Oi(e.oldest_conversation_age_days)}
            </div>
        </div>
    `}function Bu(e){return!e||!e.subdirectories||e.subdirectories.length===0?'<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available.</div>':`
        <div style="display: grid; gap: 8px; margin-bottom: 12px;">
            ${e.subdirectories.map(t=>`
                <div class="glass" style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 14px;">
                    <div style="font-weight: 600; color: hsl(var(--text-primary)); text-transform: capitalize;">${hn(t.label)}</div>
                    <div style="font-size: 13px; color: hsl(var(--text-tertiary));">
                        ${t.exists?`${Nr(t.total_size_bytes)} &middot; ${t.file_count} files`:'<span style="font-style: italic;">not present</span>'}
                    </div>
                </div>
            `).join("")}
        </div>
        <div style="font-weight: 700; color: hsl(var(--text-primary));">
            Total: ${Nr(e.total_size_bytes)} across ${e.total_file_count} files
        </div>
    `}function Nr(e){let t=Number(e)||0,n=["B","KB","MB","GB","TB"],r=0;for(;Math.abs(t)>=1024&&r<n.length-1;)t/=1024,r+=1;return`${t.toFixed(1)} ${n[r]}`}function Oi(e){return e==null?"-":e<1?`${Math.round(e*24)}h`:`${Math.round(e)}d`}function hn(e){let t=document.createElement("div");return t.textContent=e??"",t.innerHTML}var qi=M(()=>{});function Ni(){try{return JSON.parse(localStorage.getItem(Fi)||"{}")}catch{return{}}}function Hu(e){localStorage.setItem(Fi,JSON.stringify(e))}function Vi(){let e=document.querySelectorAll(".sidebar"),t=Ni();e.forEach((n,r)=>{n.querySelectorAll(".sidebar-section").forEach((o,i)=>{let a=`sidebar-${r}-section-${i}`,l=o.querySelector("h3");if(!l)return;let c=document.createElement("div");for(c.className="sidebar-section-content";l.nextSibling;)c.appendChild(l.nextSibling);o.appendChild(c),l.classList.add("sidebar-section-toggle"),l.setAttribute("role","button"),l.setAttribute("tabindex","0");let u=l.textContent.toLowerCase(),d=!u.includes("backup")&&!u.includes("system overview");(t[a]!==void 0?t[a]:d)?l.setAttribute("aria-expanded","true"):(o.classList.add("section-collapsed"),l.setAttribute("aria-expanded","false")),l.addEventListener("click",()=>{let h=o.classList.toggle("section-collapsed");l.setAttribute("aria-expanded",(!h).toString());let p=Ni();p[a]=!h,Hu(p)}),l.addEventListener("keydown",h=>{(h.key==="Enter"||h.key===" ")&&(h.preventDefault(),l.click())})})})}var Fi,Ui=M(()=>{Fi="sidebar-sections-state"});function zi(){Mu(),Ru(),Du(),Ou()}function Mu(){let e=document.querySelector(".container"),t=document.getElementById("sidebarToggle"),n=document.getElementById("rightPanelToggle");e&&(localStorage.getItem("sidebar-collapsed")==="true"&&e.classList.add("sidebar-collapsed"),localStorage.getItem("right-collapsed")==="true"&&e.classList.add("right-collapsed"),t?.addEventListener("click",()=>{e.classList.toggle("sidebar-collapsed"),localStorage.setItem("sidebar-collapsed",e.classList.contains("sidebar-collapsed"))}),n?.addEventListener("click",()=>{e.classList.toggle("right-collapsed"),localStorage.setItem("right-collapsed",e.classList.contains("right-collapsed"))}))}function Ru(){document.addEventListener("keydown",e=>{(e.metaKey||e.ctrlKey)&&e.key==="k"&&(e.preventDefault(),document.getElementById("search")?.focus())})}function Ct(){je&&(je.remove(),je=null)}function Du(){let e=new Set(["mode","sortBy"]);document.addEventListener("click",t=>{je&&!t.target.closest(".filter-chip")&&!t.target.closest(".filter-dropdown")&&Ct()}),document.addEventListener("keydown",t=>{t.key==="Escape"&&Ct()}),document.querySelectorAll(".filter-chip[data-for]").forEach(t=>{let n=t.dataset.for,r=document.getElementById(n);if(!r)return;let s=t.querySelector(".filter-value");t.addEventListener("click",i=>{if(i.stopPropagation(),je&&je.dataset.forChip===n){Ct();return}Ct();let a=document.createElement("div");a.className="filter-dropdown",a.dataset.forChip=n,Array.from(r.options).forEach((c,u)=>{let d=document.createElement("button");d.type="button",d.className="filter-dropdown-item",d.textContent=c.text,u===r.selectedIndex&&d.classList.add("selected"),d.addEventListener("click",()=>{r.selectedIndex=u,r.dispatchEvent(new Event("change")),Ct()}),a.appendChild(d)});let l=t.getBoundingClientRect();a.style.position="fixed",a.style.top=`${l.bottom+4}px`,a.style.left=`${l.left}px`,document.body.appendChild(a),je=a});function o(){let i=r.options[r.selectedIndex]?.text||"";s&&(s.textContent=i);let a=e.has(n)||r.selectedIndex>0;t.classList.toggle("active",a)}r.addEventListener("change",o),o()})}function Ou(){document.querySelectorAll(".nav-item[data-action]").forEach(e=>{e.addEventListener("click",()=>{document.querySelectorAll(".nav-item").forEach(t=>t.classList.remove("active")),e.classList.add("active")})})}var je,Wi=M(()=>{je=null});function Pu(){return`
        <svg class="clearable-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" stroke-width="2.25" stroke-linecap="round"></path>
        </svg>
    `}function ju(e){return!(!(e instanceof HTMLElement)||e.dataset.clearableOptOut==="true"||e.disabled||e.readOnly||!e.parentElement)}function qu(e,t){let n=!!(e.value&&e.value.length>0);t.hidden=!n,t.setAttribute("aria-hidden",n?"false":"true")}function Ki(e){if(!ju(e)||e.dataset.clearableBound==="true")return;let t=e.parentElement;if(!t)return;let n=document.createElement("button");n.type="button",n.className="clearable-button",n.innerHTML=Pu(),n.setAttribute("aria-label","Clear text"),n.setAttribute("title","Clear"),n.hidden=!0,e.tagName==="TEXTAREA"&&n.classList.add("is-textarea"),t.classList.add("clearable-host"),e.classList.add("clearable-input"),t.appendChild(n);let r=()=>qu(e,n);e.addEventListener("input",r),e.addEventListener("change",r),e.addEventListener("blur",r),n.addEventListener("click",()=>{e.value="",e.dispatchEvent(new Event("input",{bubbles:!0})),e.dispatchEvent(new Event("change",{bubbles:!0})),r(),e.focus()}),e.dataset.clearableBound="true",r()}function Xi(e){(e instanceof HTMLElement||e instanceof Document)&&(e instanceof HTMLElement&&e.matches(Ji)&&Ki(e),e.querySelectorAll?.(Ji).forEach(t=>{Ki(t)}))}function Qi(){Xi(document),new MutationObserver(t=>{for(let n of t)n.addedNodes.forEach(r=>{r instanceof HTMLElement&&Xi(r)})}).observe(document.body,{childList:!0,subtree:!0})}var Ji,Yi=M(()=>{Ji='input[type="text"], input[type="search"], textarea'});var Nu={};function Z(e,t){try{let n=t();n&&typeof n.then=="function"&&n.catch(r=>{console.error(`Init failed: ${e}`,r)})}catch(n){console.error(`Init failed: ${e}`,n)}}var N,Gi,Zi,ea=M(()=>{Io();Ge();kr();we();li();ur();pr();fi();vr();mi();Cr();Ei();Ci();ki();Li();Ke();Hi();Ir();Di();qi();Ui();Wi();Yi();N=window.searchatActions||(window.searchatActions={});N.search=xe;N.toggleCustomDate=nn;N.toggleHelpModal=yt;N.restoreSearchFromHistory=Lo;N.clearSearchHistory=Ao;N.copyCode=fr;N.showBookmarks=gr;N.toggleBulkMode=function(){throw new Error("Bulk export module not loaded")};N.showAnalytics=pi;N.showDashboards=_i;N.showExpertise=Or;N.showContradictions=qr;N.showDiskManager=Pi;N.goToPage=e=>Jt(e,xe);N.showAllConversations=gt;N.resumeSession=Ye;N.indexMissing=Jo;N.shutdownServer=Ko;N.createBackup=Mi;N.showBackups=Ri;N.showSearchView=Y;window.setTheme=lr;window.showExpertise=Or;window.showContradictions=qr;window.Alpine?.store?.("theme")||Z("theme",ko);Z("shortcuts",ai);Z("search-history",$o);Z("suggestions",ui);Z("bookmarks",Do);Z("saved-queries",xi);Z("project-suggestion",Lr);Z("dataset-selector",Po);Z("manage-page",Bi);Z("sidebar-sections",Vi);Z("layout",zi);Z("clearable-inputs",Qi);Z("bulk-export",async()=>{let e=await Promise.resolve().then(()=>(Er(),Fo));N.toggleBulkMode=e.toggleBulkMode,e.initBulkExport()});Gi=document.getElementById("date");Gi&&Gi.addEventListener("change",nn);Zi=document.getElementById("search");Zi&&Zi.addEventListener("keypress",e=>{e.key==="Enter"&&xe()});document.addEventListener("click",e=>{let t=e.target.closest("[data-action]");if(!t)return;let n=t.dataset.action;if(n==="saveQueryInline"){let s=document.getElementById("saveQueryButton");s&&s.click();return}let r=n?N[n]:null;typeof r=="function"&&r()});window.addEventListener("load",async()=>{let e=Zo(),t=sessionStorage.getItem("activeConversationId"),n=window.location.pathname.match(/\/conversation\/([^/]+)/),r=n&&n[1]?n[1]:t;if(r){await Ee(r,!1);return}await Xt(),sessionStorage.getItem("searchState")&&(await ie(),setTimeout(()=>{let o=sessionStorage.getItem("lastScrollPosition");o&&window.scrollTo(0,parseInt(o));let i=sessionStorage.getItem("lastResultIndex");if(i){let a=document.getElementById(`result-${i}`);a&&a.classList.add("result-highlight")}},500)),sessionStorage.removeItem("activeConversationId"),await e});window.addEventListener("popstate",async()=>{let e=window.location.pathname.match(/\/conversation\/([^/]+)/);if(e&&e[1]){await Ee(e[1],!1);return}Y(),await ie()})});var bn=!1,xn=!1,ke=[],En=-1,Mn=!1;function ra(e){ia(e)}function sa(){Mn=!0}function oa(){Mn=!1,rs()}function ia(e){ke.includes(e)||ke.push(e),rs()}function aa(e){let t=ke.indexOf(e);t!==-1&&t>En&&ke.splice(t,1)}function rs(){if(!xn&&!bn){if(Mn)return;bn=!0,queueMicrotask(la)}}function la(){bn=!1,xn=!0;for(let e=0;e<ke.length;e++)ke[e](),En=e;ke.length=0,En=-1,xn=!1}var Ve,Me,Ue,ss,wn=!0;function ca(e){wn=!1,e(),wn=!0}function da(e){Ve=e.reactive,Ue=e.release,Me=t=>e.effect(t,{scheduler:n=>{wn?ra(n):n()}}),ss=e.raw}function Vr(e){Me=e}function ua(e){let t=()=>{};return[r=>{let s=Me(r);return e._x_effects||(e._x_effects=new Set,e._x_runEffects=()=>{e._x_effects.forEach(o=>o())}),e._x_effects.add(s),t=()=>{s!==void 0&&(e._x_effects.delete(s),Ue(s))},s},()=>{t()}]}function os(e,t){let n=!0,r,s=Me(()=>{let o=e();if(JSON.stringify(o),!n&&(typeof o=="object"||o!==r)){let i=r;queueMicrotask(()=>{t(o,i)})}r=o,n=!1});return()=>Ue(s)}async function fa(e){sa();try{await e(),await Promise.resolve()}finally{oa()}}var is=[],as=[],ls=[];function pa(e){ls.push(e)}function Rn(e,t){typeof t=="function"?(e._x_cleanups||(e._x_cleanups=[]),e._x_cleanups.push(t)):(t=e,as.push(t))}function cs(e){is.push(e)}function ds(e,t,n){e._x_attributeCleanups||(e._x_attributeCleanups={}),e._x_attributeCleanups[t]||(e._x_attributeCleanups[t]=[]),e._x_attributeCleanups[t].push(n)}function us(e,t){e._x_attributeCleanups&&Object.entries(e._x_attributeCleanups).forEach(([n,r])=>{(t===void 0||t.includes(n))&&(r.forEach(s=>s()),delete e._x_attributeCleanups[n])})}function ha(e){for(e._x_effects?.forEach(aa);e._x_cleanups?.length;)e._x_cleanups.pop()()}var Dn=new MutationObserver(qn),On=!1;function Pn(){Dn.observe(document,{subtree:!0,childList:!0,attributes:!0,attributeOldValue:!0}),On=!0}function fs(){ma(),Dn.disconnect(),On=!1}var rt=[];function ma(){let e=Dn.takeRecords();rt.push(()=>e.length>0&&qn(e));let t=rt.length;queueMicrotask(()=>{if(rt.length===t)for(;rt.length>0;)rt.shift()()})}function q(e){if(!On)return e();fs();let t=e();return Pn(),t}var jn=!1,Ht=[];function ga(){jn=!0}function va(){jn=!1,qn(Ht),Ht=[]}function qn(e){if(jn){Ht=Ht.concat(e);return}let t=[],n=new Set,r=new Map,s=new Map;for(let o=0;o<e.length;o++)if(!e[o].target._x_ignoreMutationObserver&&(e[o].type==="childList"&&(e[o].removedNodes.forEach(i=>{i.nodeType===1&&i._x_marker&&n.add(i)}),e[o].addedNodes.forEach(i=>{if(i.nodeType===1){if(n.has(i)){n.delete(i);return}i._x_marker||t.push(i)}})),e[o].type==="attributes")){let i=e[o].target,a=e[o].attributeName,l=e[o].oldValue,c=()=>{r.has(i)||r.set(i,[]),r.get(i).push({name:a,value:i.getAttribute(a)})},u=()=>{s.has(i)||s.set(i,[]),s.get(i).push(a)};i.hasAttribute(a)&&l===null?c():i.hasAttribute(a)?(u(),c()):u()}s.forEach((o,i)=>{us(i,o)}),r.forEach((o,i)=>{is.forEach(a=>a(i,o))});for(let o of n)t.some(i=>i.contains(o))||as.forEach(i=>i(o));for(let o of t)o.isConnected&&ls.forEach(i=>i(o));t=null,n=null,r=null,s=null}function ps(e){return Le($e(e))}function ft(e,t,n){return e._x_dataStack=[t,...$e(n||e)],()=>{e._x_dataStack=e._x_dataStack.filter(r=>r!==t)}}function $e(e){return e._x_dataStack?e._x_dataStack:typeof ShadowRoot=="function"&&e instanceof ShadowRoot?$e(e.host):e.parentNode?$e(e.parentNode):[]}function Le(e){return new Proxy({objects:e},ya)}var ya={ownKeys({objects:e}){return Array.from(new Set(e.flatMap(t=>Object.keys(t))))},has({objects:e},t){return t==Symbol.unscopables?!1:e.some(n=>Object.prototype.hasOwnProperty.call(n,t)||Reflect.has(n,t))},get({objects:e},t,n){return t=="toJSON"?ba:Reflect.get(e.find(r=>Reflect.has(r,t))||{},t,n)},set({objects:e},t,n,r){let s=e.find(i=>Object.prototype.hasOwnProperty.call(i,t))||e[e.length-1],o=Object.getOwnPropertyDescriptor(s,t);return o?.set&&o?.get?o.set.call(r,n)||!0:Reflect.set(s,t,n)}};function ba(){return Reflect.ownKeys(this).reduce((t,n)=>(t[n]=Reflect.get(this,n),t),{})}function Nn(e){let t=r=>typeof r=="object"&&!Array.isArray(r)&&r!==null,n=(r,s="")=>{Object.entries(Object.getOwnPropertyDescriptors(r)).forEach(([o,{value:i,enumerable:a}])=>{if(a===!1||i===void 0||typeof i=="object"&&i!==null&&i.__v_skip)return;let l=s===""?o:`${s}.${o}`;typeof i=="object"&&i!==null&&i._x_interceptor?r[o]=i.initialize(e,l,o):t(i)&&i!==r&&!(i instanceof Element)&&n(i,l)})};return n(e)}function hs(e,t=()=>{}){let n={initialValue:void 0,_x_interceptor:!0,initialize(r,s,o){return e(this.initialValue,()=>xa(r,s),i=>Sn(r,s,i),s,o)}};return t(n),r=>{if(typeof r=="object"&&r!==null&&r._x_interceptor){let s=n.initialize.bind(n);n.initialize=(o,i,a)=>{let l=r.initialize(o,i,a);return n.initialValue=l,s(o,i,a)}}else n.initialValue=r;return n}}function xa(e,t){return t.split(".").reduce((n,r)=>n[r],e)}function Sn(e,t,n){if(typeof t=="string"&&(t=t.split(".")),t.length===1)e[t[0]]=n;else{if(t.length===0)throw error;return e[t[0]]||(e[t[0]]={}),Sn(e[t[0]],t.slice(1),n)}}var ms={};function se(e,t){ms[e]=t}function ct(e,t){let n=Ea(t);return Object.entries(ms).forEach(([r,s])=>{Object.defineProperty(e,`$${r}`,{get(){return s(t,n)},enumerable:!1})}),e}function Ea(e){let[t,n]=Ss(e),r={interceptor:hs,...t};return Rn(e,n),r}function wa(e,t,n,...r){try{return n(...r)}catch(s){dt(s,e,t)}}function dt(...e){return gs(...e)}var gs=_a;function Sa(e){gs=e}function _a(e,t,n=void 0){e=Object.assign(e??{message:"No error message given."},{el:t,expression:n}),console.warn(`Alpine Expression Error: ${e.message}

${n?'Expression: "'+n+`"

`:""}`,t),setTimeout(()=>{throw e},0)}var Ne=!0;function vs(e){let t=Ne;Ne=!1;let n=e();return Ne=t,n}function Ie(e,t,n={}){let r;return X(e,t)(s=>r=s,n),r}function X(...e){return ys(...e)}var ys=xs;function Ca(e){ys=e}var bs;function ka(e){bs=e}function xs(e,t){let n={};ct(n,e);let r=[n,...$e(e)],s=typeof t=="function"?Ia(r,t):Aa(r,t,e);return wa.bind(null,e,t,s)}function Ia(e,t){return(n=()=>{},{scope:r={},params:s=[],context:o}={})=>{if(!Ne){ut(n,t,Le([r,...e]),s);return}let i=t.apply(Le([r,...e]),s);ut(n,i)}}var mn={};function Ta(e,t){if(mn[e])return mn[e];let n=Object.getPrototypeOf(async function(){}).constructor,r=/^[\n\s]*if.*\(.*\)/.test(e.trim())||/^(let|const)\s/.test(e.trim())?`(async()=>{ ${e} })()`:e,o=(()=>{try{let i=new n(["__self","scope"],`with (scope) { __self.result = ${r} }; __self.finished = true; return __self.result;`);return Object.defineProperty(i,"name",{value:`[Alpine] ${e}`}),i}catch(i){return dt(i,t,e),Promise.resolve()}})();return mn[e]=o,o}function Aa(e,t,n){let r=Ta(t,n);return(s=()=>{},{scope:o={},params:i=[],context:a}={})=>{r.result=void 0,r.finished=!1;let l=Le([o,...e]);if(typeof r=="function"){let c=r.call(a,r,l).catch(u=>dt(u,n,t));r.finished?(ut(s,r.result,l,i,n),r.result=void 0):c.then(u=>{ut(s,u,l,i,n)}).catch(u=>dt(u,n,t)).finally(()=>r.result=void 0)}}}function ut(e,t,n,r,s){if(Ne&&typeof t=="function"){let o=t.apply(n,r);o instanceof Promise?o.then(i=>ut(e,i,n,r)).catch(i=>dt(i,s,t)):e(o)}else typeof t=="object"&&t instanceof Promise?t.then(o=>e(o)):e(t)}function $a(...e){return bs(...e)}function La(e,t,n={}){let r={};ct(r,e);let s=[r,...$e(e)],o=Le([n.scope??{},...s]),i=n.params??[];if(t.includes("await")){let a=Object.getPrototypeOf(async function(){}).constructor,l=/^[\n\s]*if.*\(.*\)/.test(t.trim())||/^(let|const)\s/.test(t.trim())?`(async()=>{ ${t} })()`:t;return new a(["scope"],`with (scope) { let __result = ${l}; return __result }`).call(n.context,o)}else{let a=/^[\n\s]*if.*\(.*\)/.test(t.trim())||/^(let|const)\s/.test(t.trim())?`(()=>{ ${t} })()`:t,c=new Function(["scope"],`with (scope) { let __result = ${a}; return __result }`).call(n.context,o);return typeof c=="function"&&Ne?c.apply(o,i):c}}var Fn="x-";function ze(e=""){return Fn+e}function Ba(e){Fn=e}var Mt={};function W(e,t){return Mt[e]=t,{before(n){if(!Mt[n]){console.warn(String.raw`Cannot find directive \`${n}\`. \`${e}\` will use the default order of execution`);return}let r=Ce.indexOf(n);Ce.splice(r>=0?r:Ce.indexOf("DEFAULT"),0,e)}}}function Ha(e){return Object.keys(Mt).includes(e)}function Vn(e,t,n){if(t=Array.from(t),e._x_virtualDirectives){let o=Object.entries(e._x_virtualDirectives).map(([a,l])=>({name:a,value:l})),i=Es(o);o=o.map(a=>i.find(l=>l.name===a.name)?{name:`x-bind:${a.name}`,value:`"${a.value}"`}:a),t=t.concat(o)}let r={};return t.map(ks((o,i)=>r[o]=i)).filter(Ts).map(Da(r,n)).sort(Oa).map(o=>Ra(e,o))}function Es(e){return Array.from(e).map(ks()).filter(t=>!Ts(t))}var _n=!1,it=new Map,ws=Symbol();function Ma(e){_n=!0;let t=Symbol();ws=t,it.set(t,[]);let n=()=>{for(;it.get(t).length;)it.get(t).shift()();it.delete(t)},r=()=>{_n=!1,n()};e(n),r()}function Ss(e){let t=[],n=a=>t.push(a),[r,s]=ua(e);return t.push(s),[{Alpine:Je,effect:r,cleanup:n,evaluateLater:X.bind(X,e),evaluate:Ie.bind(Ie,e)},()=>t.forEach(a=>a())]}function Ra(e,t){let n=()=>{},r=Mt[t.type]||n,[s,o]=Ss(e);ds(e,t.original,o);let i=()=>{e._x_ignore||e._x_ignoreSelf||(r.inline&&r.inline(e,t,s),r=r.bind(r,e,t,s),_n?it.get(ws).push(r):r())};return i.runCleanups=o,i}var _s=(e,t)=>({name:n,value:r})=>(n.startsWith(e)&&(n=n.replace(e,t)),{name:n,value:r}),Cs=e=>e;function ks(e=()=>{}){return({name:t,value:n})=>{let{name:r,value:s}=Is.reduce((o,i)=>i(o),{name:t,value:n});return r!==t&&e(r,t),{name:r,value:s}}}var Is=[];function Un(e){Is.push(e)}function Ts({name:e}){return As().test(e)}var As=()=>new RegExp(`^${Fn}([^:^.]+)\\b`);function Da(e,t){return({name:n,value:r})=>{n===r&&(r="");let s=n.match(As()),o=n.match(/:([a-zA-Z0-9\-_:]+)/),i=n.match(/\.[^.\]]+(?=[^\]]*$)/g)||[],a=t||e[n]||n;return{type:s?s[1]:null,value:o?o[1]:null,modifiers:i.map(l=>l.replace(".","")),expression:r,original:a}}}var Cn="DEFAULT",Ce=["ignore","ref","data","id","anchor","bind","init","for","model","modelable","transition","show","if",Cn,"teleport"];function Oa(e,t){let n=Ce.indexOf(e.type)===-1?Cn:e.type,r=Ce.indexOf(t.type)===-1?Cn:t.type;return Ce.indexOf(n)-Ce.indexOf(r)}function at(e,t,n={}){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0,cancelable:!0}))}function Be(e,t){if(typeof ShadowRoot=="function"&&e instanceof ShadowRoot){Array.from(e.children).forEach(s=>Be(s,t));return}let n=!1;if(t(e,()=>n=!0),n)return;let r=e.firstElementChild;for(;r;)Be(r,t,!1),r=r.nextElementSibling}function ee(e,...t){console.warn(`Alpine Warning: ${e}`,...t)}var Ur=!1;function Pa(){Ur&&ee("Alpine has already been initialized on this page. Calling Alpine.start() more than once can cause problems."),Ur=!0,document.body||ee("Unable to initialize. Trying to load Alpine before `<body>` is available. Did you forget to add `defer` in Alpine's `<script>` tag?"),at(document,"alpine:init"),at(document,"alpine:initializing"),Pn(),pa(t=>ue(t,Be)),Rn(t=>We(t)),cs((t,n)=>{Vn(t,n).forEach(r=>r())});let e=t=>!Dt(t.parentElement,!0);Array.from(document.querySelectorAll(Bs().join(","))).filter(e).forEach(t=>{ue(t)}),at(document,"alpine:initialized"),setTimeout(()=>{Fa()})}var zn=[],$s=[];function Ls(){return zn.map(e=>e())}function Bs(){return zn.concat($s).map(e=>e())}function Hs(e){zn.push(e)}function Ms(e){$s.push(e)}function Dt(e,t=!1){return He(e,n=>{if((t?Bs():Ls()).some(s=>n.matches(s)))return!0})}function He(e,t){if(e){if(t(e))return e;if(e._x_teleportBack&&(e=e._x_teleportBack),e.parentNode instanceof ShadowRoot)return He(e.parentNode.host,t);if(e.parentElement)return He(e.parentElement,t)}}function ja(e){return Ls().some(t=>e.matches(t))}var Rs=[];function qa(e){Rs.push(e)}var Na=1;function ue(e,t=Be,n=()=>{}){He(e,r=>r._x_ignore)||Ma(()=>{t(e,(r,s)=>{r._x_marker||(n(r,s),Rs.forEach(o=>o(r,s)),Vn(r,r.attributes).forEach(o=>o()),r._x_ignore||(r._x_marker=Na++),r._x_ignore&&s())})})}function We(e,t=Be){t(e,n=>{ha(n),us(n),delete n._x_marker})}function Fa(){[["ui","dialog",["[x-dialog], [x-popover]"]],["anchor","anchor",["[x-anchor]"]],["sort","sort",["[x-sort]"]]].forEach(([t,n,r])=>{Ha(n)||r.some(s=>{if(document.querySelector(s))return ee(`found "${s}", but missing ${t} plugin`),!0})})}var kn=[],Wn=!1;function Jn(e=()=>{}){return queueMicrotask(()=>{Wn||setTimeout(()=>{In()})}),new Promise(t=>{kn.push(()=>{e(),t()})})}function In(){for(Wn=!1;kn.length;)kn.shift()()}function Va(){Wn=!0}function Kn(e,t){return Array.isArray(t)?zr(e,t.join(" ")):typeof t=="object"&&t!==null?Ua(e,t):typeof t=="function"?Kn(e,t()):zr(e,t)}function zr(e,t){let n=o=>o.split(" ").filter(Boolean),r=o=>o.split(" ").filter(i=>!e.classList.contains(i)).filter(Boolean),s=o=>(e.classList.add(...o),()=>{e.classList.remove(...o)});return t=t===!0?t="":t||"",s(r(t))}function Ua(e,t){let n=a=>a.split(" ").filter(Boolean),r=Object.entries(t).flatMap(([a,l])=>l?n(a):!1).filter(Boolean),s=Object.entries(t).flatMap(([a,l])=>l?!1:n(a)).filter(Boolean),o=[],i=[];return s.forEach(a=>{e.classList.contains(a)&&(e.classList.remove(a),i.push(a))}),r.forEach(a=>{e.classList.contains(a)||(e.classList.add(a),o.push(a))}),()=>{i.forEach(a=>e.classList.add(a)),o.forEach(a=>e.classList.remove(a))}}function Ot(e,t){return typeof t=="object"&&t!==null?za(e,t):Wa(e,t)}function za(e,t){let n={};return Object.entries(t).forEach(([r,s])=>{n[r]=e.style[r],r.startsWith("--")||(r=Ja(r)),e.style.setProperty(r,s)}),setTimeout(()=>{e.style.length===0&&e.removeAttribute("style")}),()=>{Ot(e,n)}}function Wa(e,t){let n=e.getAttribute("style",t);return e.setAttribute("style",t),()=>{e.setAttribute("style",n||"")}}function Ja(e){return e.replace(/([a-z])([A-Z])/g,"$1-$2").toLowerCase()}function Tn(e,t=()=>{}){let n=!1;return function(){n?t.apply(this,arguments):(n=!0,e.apply(this,arguments))}}W("transition",(e,{value:t,modifiers:n,expression:r},{evaluate:s})=>{typeof r=="function"&&(r=s(r)),r!==!1&&(!r||typeof r=="boolean"?Xa(e,n,t):Ka(e,r,t))});function Ka(e,t,n){Ds(e,Kn,""),{enter:s=>{e._x_transition.enter.during=s},"enter-start":s=>{e._x_transition.enter.start=s},"enter-end":s=>{e._x_transition.enter.end=s},leave:s=>{e._x_transition.leave.during=s},"leave-start":s=>{e._x_transition.leave.start=s},"leave-end":s=>{e._x_transition.leave.end=s}}[n](t)}function Xa(e,t,n){Ds(e,Ot);let r=!t.includes("in")&&!t.includes("out")&&!n,s=r||t.includes("in")||["enter"].includes(n),o=r||t.includes("out")||["leave"].includes(n);t.includes("in")&&!r&&(t=t.filter((v,y)=>y<t.indexOf("out"))),t.includes("out")&&!r&&(t=t.filter((v,y)=>y>t.indexOf("out")));let i=!t.includes("opacity")&&!t.includes("scale"),a=i||t.includes("opacity"),l=i||t.includes("scale"),c=a?0:1,u=l?st(t,"scale",95)/100:1,d=st(t,"delay",0)/1e3,f=st(t,"origin","center"),h="opacity, transform",p=st(t,"duration",150)/1e3,g=st(t,"duration",75)/1e3,m="cubic-bezier(0.4, 0.0, 0.2, 1)";s&&(e._x_transition.enter.during={transformOrigin:f,transitionDelay:`${d}s`,transitionProperty:h,transitionDuration:`${p}s`,transitionTimingFunction:m},e._x_transition.enter.start={opacity:c,transform:`scale(${u})`},e._x_transition.enter.end={opacity:1,transform:"scale(1)"}),o&&(e._x_transition.leave.during={transformOrigin:f,transitionDelay:`${d}s`,transitionProperty:h,transitionDuration:`${g}s`,transitionTimingFunction:m},e._x_transition.leave.start={opacity:1,transform:"scale(1)"},e._x_transition.leave.end={opacity:c,transform:`scale(${u})`})}function Ds(e,t,n={}){e._x_transition||(e._x_transition={enter:{during:n,start:n,end:n},leave:{during:n,start:n,end:n},in(r=()=>{},s=()=>{}){An(e,t,{during:this.enter.during,start:this.enter.start,end:this.enter.end},r,s)},out(r=()=>{},s=()=>{}){An(e,t,{during:this.leave.during,start:this.leave.start,end:this.leave.end},r,s)}})}window.Element.prototype._x_toggleAndCascadeWithTransitions=function(e,t,n,r){let s=document.visibilityState==="visible"?requestAnimationFrame:setTimeout,o=()=>s(n);if(t){e._x_transition&&(e._x_transition.enter||e._x_transition.leave)?e._x_transition.enter&&(Object.entries(e._x_transition.enter.during).length||Object.entries(e._x_transition.enter.start).length||Object.entries(e._x_transition.enter.end).length)?e._x_transition.in(n):o():e._x_transition?e._x_transition.in(n):o();return}e._x_hidePromise=e._x_transition?new Promise((i,a)=>{e._x_transition.out(()=>{},()=>i(r)),e._x_transitioning&&e._x_transitioning.beforeCancel(()=>a({isFromCancelledTransition:!0}))}):Promise.resolve(r),queueMicrotask(()=>{let i=Os(e);i?(i._x_hideChildren||(i._x_hideChildren=[]),i._x_hideChildren.push(e)):s(()=>{let a=l=>{let c=Promise.all([l._x_hidePromise,...(l._x_hideChildren||[]).map(a)]).then(([u])=>u?.());return delete l._x_hidePromise,delete l._x_hideChildren,c};a(e).catch(l=>{if(!l.isFromCancelledTransition)throw l})})})};function Os(e){let t=e.parentNode;if(t)return t._x_hidePromise?t:Os(t)}function An(e,t,{during:n,start:r,end:s}={},o=()=>{},i=()=>{}){if(e._x_transitioning&&e._x_transitioning.cancel(),Object.keys(n).length===0&&Object.keys(r).length===0&&Object.keys(s).length===0){o(),i();return}let a,l,c;Qa(e,{start(){a=t(e,r)},during(){l=t(e,n)},before:o,end(){a(),c=t(e,s)},after:i,cleanup(){l(),c()}})}function Qa(e,t){let n,r,s,o=Tn(()=>{q(()=>{n=!0,r||t.before(),s||(t.end(),In()),t.after(),e.isConnected&&t.cleanup(),delete e._x_transitioning})});e._x_transitioning={beforeCancels:[],beforeCancel(i){this.beforeCancels.push(i)},cancel:Tn(function(){for(;this.beforeCancels.length;)this.beforeCancels.shift()();o()}),finish:o},q(()=>{t.start(),t.during()}),Va(),requestAnimationFrame(()=>{if(n)return;let i=Number(getComputedStyle(e).transitionDuration.replace(/,.*/,"").replace("s",""))*1e3,a=Number(getComputedStyle(e).transitionDelay.replace(/,.*/,"").replace("s",""))*1e3;i===0&&(i=Number(getComputedStyle(e).animationDuration.replace("s",""))*1e3),q(()=>{t.before()}),r=!0,requestAnimationFrame(()=>{n||(q(()=>{t.end()}),In(),setTimeout(e._x_transitioning.finish,i+a),s=!0)})})}function st(e,t,n){if(e.indexOf(t)===-1)return n;let r=e[e.indexOf(t)+1];if(!r||t==="scale"&&isNaN(r))return n;if(t==="duration"||t==="delay"){let s=r.match(/([0-9]+)ms/);if(s)return s[1]}return t==="origin"&&["top","right","left","center","bottom"].includes(e[e.indexOf(t)+2])?[r,e[e.indexOf(t)+2]].join(" "):r}var ve=!1;function be(e,t=()=>{}){return(...n)=>ve?t(...n):e(...n)}function Ya(e){return(...t)=>ve&&e(...t)}var Ps=[];function Pt(e){Ps.push(e)}function Ga(e,t){Ps.forEach(n=>n(e,t)),ve=!0,js(()=>{ue(t,(n,r)=>{r(n,()=>{})})}),ve=!1}var $n=!1;function Za(e,t){t._x_dataStack||(t._x_dataStack=e._x_dataStack),ve=!0,$n=!0,js(()=>{el(t)}),ve=!1,$n=!1}function el(e){let t=!1;ue(e,(r,s)=>{Be(r,(o,i)=>{if(t&&ja(o))return i();t=!0,s(o,i)})})}function js(e){let t=Me;Vr((n,r)=>{let s=t(n);return Ue(s),()=>{}}),e(),Vr(t)}function qs(e,t,n,r=[]){switch(e._x_bindings||(e._x_bindings=Ve({})),e._x_bindings[t]=n,t=r.includes("camel")?ll(t):t,t){case"value":tl(e,n);break;case"style":rl(e,n);break;case"class":nl(e,n);break;case"selected":case"checked":sl(e,t,n);break;default:Ns(e,t,n);break}}function tl(e,t){if(Us(e))e.attributes.value===void 0&&(e.value=t),window.fromModel&&(typeof t=="boolean"?e.checked=Bt(e.value)===t:e.checked=Wr(e.value,t));else if(Xn(e))Number.isInteger(t)?e.value=t:!Array.isArray(t)&&typeof t!="boolean"&&![null,void 0].includes(t)?e.value=String(t):Array.isArray(t)?e.checked=t.some(n=>Wr(n,e.value)):e.checked=!!t;else if(e.tagName==="SELECT")al(e,t);else{if(e.value===t)return;e.value=t===void 0?"":t}}function nl(e,t){e._x_undoAddedClasses&&e._x_undoAddedClasses(),e._x_undoAddedClasses=Kn(e,t)}function rl(e,t){e._x_undoAddedStyles&&e._x_undoAddedStyles(),e._x_undoAddedStyles=Ot(e,t)}function sl(e,t,n){Ns(e,t,n),il(e,t,n)}function Ns(e,t,n){[null,void 0,!1].includes(n)&&dl(t)?e.removeAttribute(t):(Fs(t)&&(n=t),ol(e,t,n))}function ol(e,t,n){e.getAttribute(t)!=n&&e.setAttribute(t,n)}function il(e,t,n){e[t]!==n&&(e[t]=n)}function al(e,t){let n=[].concat(t).map(r=>r+"");Array.from(e.options).forEach(r=>{r.selected=n.includes(r.value)})}function ll(e){return e.toLowerCase().replace(/-(\w)/g,(t,n)=>n.toUpperCase())}function Wr(e,t){return e==t}function Bt(e){return[1,"1","true","on","yes",!0].includes(e)?!0:[0,"0","false","off","no",!1].includes(e)?!1:e?!!e:null}var cl=new Set(["allowfullscreen","async","autofocus","autoplay","checked","controls","default","defer","disabled","formnovalidate","inert","ismap","itemscope","loop","multiple","muted","nomodule","novalidate","open","playsinline","readonly","required","reversed","selected","shadowrootclonable","shadowrootdelegatesfocus","shadowrootserializable"]);function Fs(e){return cl.has(e)}function dl(e){return!["aria-pressed","aria-checked","aria-expanded","aria-selected"].includes(e)}function ul(e,t,n){return e._x_bindings&&e._x_bindings[t]!==void 0?e._x_bindings[t]:Vs(e,t,n)}function fl(e,t,n,r=!0){if(e._x_bindings&&e._x_bindings[t]!==void 0)return e._x_bindings[t];if(e._x_inlineBindings&&e._x_inlineBindings[t]!==void 0){let s=e._x_inlineBindings[t];return s.extract=r,vs(()=>Ie(e,s.expression))}return Vs(e,t,n)}function Vs(e,t,n){let r=e.getAttribute(t);return r===null?typeof n=="function"?n():n:r===""?!0:Fs(t)?!![t,"true"].includes(r):r}function Xn(e){return e.type==="checkbox"||e.localName==="ui-checkbox"||e.localName==="ui-switch"}function Us(e){return e.type==="radio"||e.localName==="ui-radio"}function zs(e,t){let n;return function(){let r=this,s=arguments,o=function(){n=null,e.apply(r,s)};clearTimeout(n),n=setTimeout(o,t)}}function Ws(e,t){let n;return function(){let r=this,s=arguments;n||(e.apply(r,s),n=!0,setTimeout(()=>n=!1,t))}}function Js({get:e,set:t},{get:n,set:r}){let s=!0,o,i,a=Me(()=>{let l=e(),c=n();if(s)r(gn(l)),s=!1;else{let u=JSON.stringify(l),d=JSON.stringify(c);u!==o?r(gn(l)):u!==d&&t(gn(c))}o=JSON.stringify(e()),i=JSON.stringify(n())});return()=>{Ue(a)}}function gn(e){return typeof e=="object"?JSON.parse(JSON.stringify(e)):e}function pl(e){(Array.isArray(e)?e:[e]).forEach(n=>n(Je))}var _e={},Jr=!1;function hl(e,t){if(Jr||(_e=Ve(_e),Jr=!0),t===void 0)return _e[e];_e[e]=t,Nn(_e[e]),typeof t=="object"&&t!==null&&t.hasOwnProperty("init")&&typeof t.init=="function"&&_e[e].init()}function ml(){return _e}var Ks={};function gl(e,t){let n=typeof t!="function"?()=>t:t;return e instanceof Element?Xs(e,n()):(Ks[e]=n,()=>{})}function vl(e){return Object.entries(Ks).forEach(([t,n])=>{Object.defineProperty(e,t,{get(){return(...r)=>n(...r)}})}),e}function Xs(e,t,n){let r=[];for(;r.length;)r.pop()();let s=Object.entries(t).map(([i,a])=>({name:i,value:a})),o=Es(s);return s=s.map(i=>o.find(a=>a.name===i.name)?{name:`x-bind:${i.name}`,value:`"${i.value}"`}:i),Vn(e,s,n).map(i=>{r.push(i.runCleanups),i()}),()=>{for(;r.length;)r.pop()()}}var Qs={};function yl(e,t){Qs[e]=t}function bl(e,t){return Object.entries(Qs).forEach(([n,r])=>{Object.defineProperty(e,n,{get(){return(...s)=>r.bind(t)(...s)},enumerable:!1})}),e}var xl={get reactive(){return Ve},get release(){return Ue},get effect(){return Me},get raw(){return ss},get transaction(){return fa},version:"3.15.8",flushAndStopDeferringMutations:va,dontAutoEvaluateFunctions:vs,disableEffectScheduling:ca,startObservingMutations:Pn,stopObservingMutations:fs,setReactivityEngine:da,onAttributeRemoved:ds,onAttributesAdded:cs,closestDataStack:$e,skipDuringClone:be,onlyDuringClone:Ya,addRootSelector:Hs,addInitSelector:Ms,setErrorHandler:Sa,interceptClone:Pt,addScopeToNode:ft,deferMutations:ga,mapAttributes:Un,evaluateLater:X,interceptInit:qa,initInterceptors:Nn,injectMagics:ct,setEvaluator:Ca,setRawEvaluator:ka,mergeProxies:Le,extractProp:fl,findClosest:He,onElRemoved:Rn,closestRoot:Dt,destroyTree:We,interceptor:hs,transition:An,setStyles:Ot,mutateDom:q,directive:W,entangle:Js,throttle:Ws,debounce:zs,evaluate:Ie,evaluateRaw:$a,initTree:ue,nextTick:Jn,prefixed:ze,prefix:Ba,plugin:pl,magic:se,store:hl,start:Pa,clone:Za,cloneNode:Ga,bound:ul,$data:ps,watch:os,walk:Be,data:yl,bind:gl},Je=xl;function Ys(e,t){let n=Object.create(null),r=e.split(",");for(let s=0;s<r.length;s++)n[r[s]]=!0;return t?s=>!!n[s.toLowerCase()]:s=>!!n[s]}var El="itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly",Vu=Ys(El+",async,autofocus,autoplay,controls,default,defer,disabled,hidden,loop,open,required,reversed,scoped,seamless,checked,muted,multiple,selected"),wl=Object.freeze({}),Uu=Object.freeze([]),Sl=Object.prototype.hasOwnProperty,jt=(e,t)=>Sl.call(e,t),Te=Array.isArray,lt=e=>Gs(e)==="[object Map]",_l=e=>typeof e=="string",Qn=e=>typeof e=="symbol",qt=e=>e!==null&&typeof e=="object",Cl=Object.prototype.toString,Gs=e=>Cl.call(e),Zs=e=>Gs(e).slice(8,-1),Yn=e=>_l(e)&&e!=="NaN"&&e[0]!=="-"&&""+parseInt(e,10)===e,Nt=e=>{let t=Object.create(null);return n=>t[n]||(t[n]=e(n))},kl=/-(\w)/g,zu=Nt(e=>e.replace(kl,(t,n)=>n?n.toUpperCase():"")),Il=/\B([A-Z])/g,Wu=Nt(e=>e.replace(Il,"-$1").toLowerCase()),eo=Nt(e=>e.charAt(0).toUpperCase()+e.slice(1)),Ju=Nt(e=>e?`on${eo(e)}`:""),to=(e,t)=>e!==t&&(e===e||t===t),Ln=new WeakMap,ot=[],le,Ae=Symbol("iterate"),Bn=Symbol("Map key iterate");function Tl(e){return e&&e._isEffect===!0}function Al(e,t=wl){Tl(e)&&(e=e.raw);let n=Bl(e,t);return t.lazy||n(),n}function $l(e){e.active&&(no(e),e.options.onStop&&e.options.onStop(),e.active=!1)}var Ll=0;function Bl(e,t){let n=function(){if(!n.active)return e();if(!ot.includes(n)){no(n);try{return Ml(),ot.push(n),le=n,e()}finally{ot.pop(),ro(),le=ot[ot.length-1]}}};return n.id=Ll++,n.allowRecurse=!!t.allowRecurse,n._isEffect=!0,n.active=!0,n.raw=e,n.deps=[],n.options=t,n}function no(e){let{deps:t}=e;if(t.length){for(let n=0;n<t.length;n++)t[n].delete(e);t.length=0}}var Fe=!0,Gn=[];function Hl(){Gn.push(Fe),Fe=!1}function Ml(){Gn.push(Fe),Fe=!0}function ro(){let e=Gn.pop();Fe=e===void 0?!0:e}function re(e,t,n){if(!Fe||le===void 0)return;let r=Ln.get(e);r||Ln.set(e,r=new Map);let s=r.get(n);s||r.set(n,s=new Set),s.has(le)||(s.add(le),le.deps.push(s),le.options.onTrack&&le.options.onTrack({effect:le,target:e,type:t,key:n}))}function ye(e,t,n,r,s,o){let i=Ln.get(e);if(!i)return;let a=new Set,l=u=>{u&&u.forEach(d=>{(d!==le||d.allowRecurse)&&a.add(d)})};if(t==="clear")i.forEach(l);else if(n==="length"&&Te(e))i.forEach((u,d)=>{(d==="length"||d>=r)&&l(u)});else switch(n!==void 0&&l(i.get(n)),t){case"add":Te(e)?Yn(n)&&l(i.get("length")):(l(i.get(Ae)),lt(e)&&l(i.get(Bn)));break;case"delete":Te(e)||(l(i.get(Ae)),lt(e)&&l(i.get(Bn)));break;case"set":lt(e)&&l(i.get(Ae));break}let c=u=>{u.options.onTrigger&&u.options.onTrigger({effect:u,target:e,key:n,type:t,newValue:r,oldValue:s,oldTarget:o}),u.options.scheduler?u.options.scheduler(u):u()};a.forEach(c)}var Rl=Ys("__proto__,__v_isRef,__isVue"),so=new Set(Object.getOwnPropertyNames(Symbol).map(e=>Symbol[e]).filter(Qn)),Dl=oo(),Ol=oo(!0),Kr=Pl();function Pl(){let e={};return["includes","indexOf","lastIndexOf"].forEach(t=>{e[t]=function(...n){let r=O(this);for(let o=0,i=this.length;o<i;o++)re(r,"get",o+"");let s=r[t](...n);return s===-1||s===!1?r[t](...n.map(O)):s}}),["push","pop","shift","unshift","splice"].forEach(t=>{e[t]=function(...n){Hl();let r=O(this)[t].apply(this,n);return ro(),r}}),e}function oo(e=!1,t=!1){return function(r,s,o){if(s==="__v_isReactive")return!e;if(s==="__v_isReadonly")return e;if(s==="__v_raw"&&o===(e?t?ec:co:t?Zl:lo).get(r))return r;let i=Te(r);if(!e&&i&&jt(Kr,s))return Reflect.get(Kr,s,o);let a=Reflect.get(r,s,o);return(Qn(s)?so.has(s):Rl(s))||(e||re(r,"get",s),t)?a:Hn(a)?!i||!Yn(s)?a.value:a:qt(a)?e?uo(a):nr(a):a}}var jl=ql();function ql(e=!1){return function(n,r,s,o){let i=n[r];if(!e&&(s=O(s),i=O(i),!Te(n)&&Hn(i)&&!Hn(s)))return i.value=s,!0;let a=Te(n)&&Yn(r)?Number(r)<n.length:jt(n,r),l=Reflect.set(n,r,s,o);return n===O(o)&&(a?to(s,i)&&ye(n,"set",r,s,i):ye(n,"add",r,s)),l}}function Nl(e,t){let n=jt(e,t),r=e[t],s=Reflect.deleteProperty(e,t);return s&&n&&ye(e,"delete",t,void 0,r),s}function Fl(e,t){let n=Reflect.has(e,t);return(!Qn(t)||!so.has(t))&&re(e,"has",t),n}function Vl(e){return re(e,"iterate",Te(e)?"length":Ae),Reflect.ownKeys(e)}var Ul={get:Dl,set:jl,deleteProperty:Nl,has:Fl,ownKeys:Vl},zl={get:Ol,set(e,t){return console.warn(`Set operation on key "${String(t)}" failed: target is readonly.`,e),!0},deleteProperty(e,t){return console.warn(`Delete operation on key "${String(t)}" failed: target is readonly.`,e),!0}},Zn=e=>qt(e)?nr(e):e,er=e=>qt(e)?uo(e):e,tr=e=>e,Ft=e=>Reflect.getPrototypeOf(e);function kt(e,t,n=!1,r=!1){e=e.__v_raw;let s=O(e),o=O(t);t!==o&&!n&&re(s,"get",t),!n&&re(s,"get",o);let{has:i}=Ft(s),a=r?tr:n?er:Zn;if(i.call(s,t))return a(e.get(t));if(i.call(s,o))return a(e.get(o));e!==s&&e.get(t)}function It(e,t=!1){let n=this.__v_raw,r=O(n),s=O(e);return e!==s&&!t&&re(r,"has",e),!t&&re(r,"has",s),e===s?n.has(e):n.has(e)||n.has(s)}function Tt(e,t=!1){return e=e.__v_raw,!t&&re(O(e),"iterate",Ae),Reflect.get(e,"size",e)}function Xr(e){e=O(e);let t=O(this);return Ft(t).has.call(t,e)||(t.add(e),ye(t,"add",e,e)),this}function Qr(e,t){t=O(t);let n=O(this),{has:r,get:s}=Ft(n),o=r.call(n,e);o?ao(n,r,e):(e=O(e),o=r.call(n,e));let i=s.call(n,e);return n.set(e,t),o?to(t,i)&&ye(n,"set",e,t,i):ye(n,"add",e,t),this}function Yr(e){let t=O(this),{has:n,get:r}=Ft(t),s=n.call(t,e);s?ao(t,n,e):(e=O(e),s=n.call(t,e));let o=r?r.call(t,e):void 0,i=t.delete(e);return s&&ye(t,"delete",e,void 0,o),i}function Gr(){let e=O(this),t=e.size!==0,n=lt(e)?new Map(e):new Set(e),r=e.clear();return t&&ye(e,"clear",void 0,void 0,n),r}function At(e,t){return function(r,s){let o=this,i=o.__v_raw,a=O(i),l=t?tr:e?er:Zn;return!e&&re(a,"iterate",Ae),i.forEach((c,u)=>r.call(s,l(c),l(u),o))}}function $t(e,t,n){return function(...r){let s=this.__v_raw,o=O(s),i=lt(o),a=e==="entries"||e===Symbol.iterator&&i,l=e==="keys"&&i,c=s[e](...r),u=n?tr:t?er:Zn;return!t&&re(o,"iterate",l?Bn:Ae),{next(){let{value:d,done:f}=c.next();return f?{value:d,done:f}:{value:a?[u(d[0]),u(d[1])]:u(d),done:f}},[Symbol.iterator](){return this}}}}function ge(e){return function(...t){{let n=t[0]?`on key "${t[0]}" `:"";console.warn(`${eo(e)} operation ${n}failed: target is readonly.`,O(this))}return e==="delete"?!1:this}}function Wl(){let e={get(o){return kt(this,o)},get size(){return Tt(this)},has:It,add:Xr,set:Qr,delete:Yr,clear:Gr,forEach:At(!1,!1)},t={get(o){return kt(this,o,!1,!0)},get size(){return Tt(this)},has:It,add:Xr,set:Qr,delete:Yr,clear:Gr,forEach:At(!1,!0)},n={get(o){return kt(this,o,!0)},get size(){return Tt(this,!0)},has(o){return It.call(this,o,!0)},add:ge("add"),set:ge("set"),delete:ge("delete"),clear:ge("clear"),forEach:At(!0,!1)},r={get(o){return kt(this,o,!0,!0)},get size(){return Tt(this,!0)},has(o){return It.call(this,o,!0)},add:ge("add"),set:ge("set"),delete:ge("delete"),clear:ge("clear"),forEach:At(!0,!0)};return["keys","values","entries",Symbol.iterator].forEach(o=>{e[o]=$t(o,!1,!1),n[o]=$t(o,!0,!1),t[o]=$t(o,!1,!0),r[o]=$t(o,!0,!0)}),[e,n,t,r]}var[Jl,Kl,Xl,Ql]=Wl();function io(e,t){let n=t?e?Ql:Xl:e?Kl:Jl;return(r,s,o)=>s==="__v_isReactive"?!e:s==="__v_isReadonly"?e:s==="__v_raw"?r:Reflect.get(jt(n,s)&&s in r?n:r,s,o)}var Yl={get:io(!1,!1)},Gl={get:io(!0,!1)};function ao(e,t,n){let r=O(n);if(r!==n&&t.call(e,r)){let s=Zs(e);console.warn(`Reactive ${s} contains both the raw and reactive versions of the same object${s==="Map"?" as keys":""}, which can lead to inconsistencies. Avoid differentiating between the raw and reactive versions of an object and only use the reactive version if possible.`)}}var lo=new WeakMap,Zl=new WeakMap,co=new WeakMap,ec=new WeakMap;function tc(e){switch(e){case"Object":case"Array":return 1;case"Map":case"Set":case"WeakMap":case"WeakSet":return 2;default:return 0}}function nc(e){return e.__v_skip||!Object.isExtensible(e)?0:tc(Zs(e))}function nr(e){return e&&e.__v_isReadonly?e:fo(e,!1,Ul,Yl,lo)}function uo(e){return fo(e,!0,zl,Gl,co)}function fo(e,t,n,r,s){if(!qt(e))return console.warn(`value cannot be made reactive: ${String(e)}`),e;if(e.__v_raw&&!(t&&e.__v_isReactive))return e;let o=s.get(e);if(o)return o;let i=nc(e);if(i===0)return e;let a=new Proxy(e,i===2?r:n);return s.set(e,a),a}function O(e){return e&&O(e.__v_raw)||e}function Hn(e){return!!(e&&e.__v_isRef===!0)}se("nextTick",()=>Jn);se("dispatch",e=>at.bind(at,e));se("watch",(e,{evaluateLater:t,cleanup:n})=>(r,s)=>{let o=t(r),a=os(()=>{let l;return o(c=>l=c),l},s);n(a)});se("store",ml);se("data",e=>ps(e));se("root",e=>Dt(e));se("refs",e=>(e._x_refs_proxy||(e._x_refs_proxy=Le(rc(e))),e._x_refs_proxy));function rc(e){let t=[];return He(e,n=>{n._x_refs&&t.push(n._x_refs)}),t}var vn={};function po(e){return vn[e]||(vn[e]=0),++vn[e]}function sc(e,t){return He(e,n=>{if(n._x_ids&&n._x_ids[t])return!0})}function oc(e,t){e._x_ids||(e._x_ids={}),e._x_ids[t]||(e._x_ids[t]=po(t))}se("id",(e,{cleanup:t})=>(n,r=null)=>{let s=`${n}${r?`-${r}`:""}`;return ic(e,s,t,()=>{let o=sc(e,n),i=o?o._x_ids[n]:po(n);return r?`${n}-${i}-${r}`:`${n}-${i}`})});Pt((e,t)=>{e._x_id&&(t._x_id=e._x_id)});function ic(e,t,n,r){if(e._x_id||(e._x_id={}),e._x_id[t])return e._x_id[t];let s=r();return e._x_id[t]=s,n(()=>{delete e._x_id[t]}),s}se("el",e=>e);ho("Focus","focus","focus");ho("Persist","persist","persist");function ho(e,t,n){se(t,r=>ee(`You can't use [$${t}] without first installing the "${e}" plugin here: https://alpinejs.dev/plugins/${n}`,r))}W("modelable",(e,{expression:t},{effect:n,evaluateLater:r,cleanup:s})=>{let o=r(t),i=()=>{let u;return o(d=>u=d),u},a=r(`${t} = __placeholder`),l=u=>a(()=>{},{scope:{__placeholder:u}}),c=i();l(c),queueMicrotask(()=>{if(!e._x_model)return;e._x_removeModelListeners.default();let u=e._x_model.get,d=e._x_model.set,f=Js({get(){return u()},set(h){d(h)}},{get(){return i()},set(h){l(h)}});s(f)})});W("teleport",(e,{modifiers:t,expression:n},{cleanup:r})=>{e.tagName.toLowerCase()!=="template"&&ee("x-teleport can only be used on a <template> tag",e);let s=Zr(n),o=e.content.cloneNode(!0).firstElementChild;e._x_teleport=o,o._x_teleportBack=e,e.setAttribute("data-teleport-template",!0),o.setAttribute("data-teleport-target",!0),e._x_forwardEvents&&e._x_forwardEvents.forEach(a=>{o.addEventListener(a,l=>{l.stopPropagation(),e.dispatchEvent(new l.constructor(l.type,l))})}),ft(o,{},e);let i=(a,l,c)=>{c.includes("prepend")?l.parentNode.insertBefore(a,l):c.includes("append")?l.parentNode.insertBefore(a,l.nextSibling):l.appendChild(a)};q(()=>{i(o,s,t),be(()=>{ue(o)})()}),e._x_teleportPutBack=()=>{let a=Zr(n);q(()=>{i(e._x_teleport,a,t)})},r(()=>q(()=>{o.remove(),We(o)}))});var ac=document.createElement("div");function Zr(e){let t=be(()=>document.querySelector(e),()=>ac)();return t||ee(`Cannot find x-teleport element for selector: "${e}"`),t}var mo=()=>{};mo.inline=(e,{modifiers:t},{cleanup:n})=>{t.includes("self")?e._x_ignoreSelf=!0:e._x_ignore=!0,n(()=>{t.includes("self")?delete e._x_ignoreSelf:delete e._x_ignore})};W("ignore",mo);W("effect",be((e,{expression:t},{effect:n})=>{n(X(e,t))}));function qe(e,t,n,r){let s=e,o=l=>r(l),i={},a=(l,c)=>u=>c(l,u);if(n.includes("dot")&&(t=lc(t)),n.includes("camel")&&(t=cc(t)),n.includes("passive")&&(i.passive=!0),n.includes("capture")&&(i.capture=!0),n.includes("window")&&(s=window),n.includes("document")&&(s=document),n.includes("debounce")){let l=n[n.indexOf("debounce")+1]||"invalid-wait",c=Rt(l.split("ms")[0])?Number(l.split("ms")[0]):250;o=zs(o,c)}if(n.includes("throttle")){let l=n[n.indexOf("throttle")+1]||"invalid-wait",c=Rt(l.split("ms")[0])?Number(l.split("ms")[0]):250;o=Ws(o,c)}return n.includes("prevent")&&(o=a(o,(l,c)=>{c.preventDefault(),l(c)})),n.includes("stop")&&(o=a(o,(l,c)=>{c.stopPropagation(),l(c)})),n.includes("once")&&(o=a(o,(l,c)=>{l(c),s.removeEventListener(t,o,i)})),(n.includes("away")||n.includes("outside"))&&(s=document,o=a(o,(l,c)=>{e.contains(c.target)||c.target.isConnected!==!1&&(e.offsetWidth<1&&e.offsetHeight<1||e._x_isShown!==!1&&l(c))})),n.includes("self")&&(o=a(o,(l,c)=>{c.target===e&&l(c)})),t==="submit"&&(o=a(o,(l,c)=>{c.target._x_pendingModelUpdates&&c.target._x_pendingModelUpdates.forEach(u=>u()),l(c)})),(uc(t)||go(t))&&(o=a(o,(l,c)=>{fc(c,n)||l(c)})),s.addEventListener(t,o,i),()=>{s.removeEventListener(t,o,i)}}function lc(e){return e.replace(/-/g,".")}function cc(e){return e.toLowerCase().replace(/-(\w)/g,(t,n)=>n.toUpperCase())}function Rt(e){return!Array.isArray(e)&&!isNaN(e)}function dc(e){return[" ","_"].includes(e)?e:e.replace(/([a-z])([A-Z])/g,"$1-$2").replace(/[_\s]/,"-").toLowerCase()}function uc(e){return["keydown","keyup"].includes(e)}function go(e){return["contextmenu","click","mouse"].some(t=>e.includes(t))}function fc(e,t){let n=t.filter(o=>!["window","document","prevent","stop","once","capture","self","away","outside","passive","preserve-scroll","blur","change","lazy"].includes(o));if(n.includes("debounce")){let o=n.indexOf("debounce");n.splice(o,Rt((n[o+1]||"invalid-wait").split("ms")[0])?2:1)}if(n.includes("throttle")){let o=n.indexOf("throttle");n.splice(o,Rt((n[o+1]||"invalid-wait").split("ms")[0])?2:1)}if(n.length===0||n.length===1&&es(e.key).includes(n[0]))return!1;let s=["ctrl","shift","alt","meta","cmd","super"].filter(o=>n.includes(o));return n=n.filter(o=>!s.includes(o)),!(s.length>0&&s.filter(i=>((i==="cmd"||i==="super")&&(i="meta"),e[`${i}Key`])).length===s.length&&(go(e.type)||es(e.key).includes(n[0])))}function es(e){if(!e)return[];e=dc(e);let t={ctrl:"control",slash:"/",space:" ",spacebar:" ",cmd:"meta",esc:"escape",up:"arrow-up",down:"arrow-down",left:"arrow-left",right:"arrow-right",period:".",comma:",",equal:"=",minus:"-",underscore:"_"};return t[e]=e,Object.keys(t).map(n=>{if(t[n]===e)return n}).filter(n=>n)}W("model",(e,{modifiers:t,expression:n},{effect:r,cleanup:s})=>{let o=e;t.includes("parent")&&(o=e.parentNode);let i=X(o,n),a;typeof n=="string"?a=X(o,`${n} = __placeholder`):typeof n=="function"&&typeof n()=="string"?a=X(o,`${n()} = __placeholder`):a=()=>{};let l=()=>{let g;return i(m=>g=m),ts(g)?g.get():g},c=g=>{let m;i(v=>m=v),ts(m)?m.set(g):a(()=>{},{scope:{__placeholder:g}})};typeof n=="string"&&e.type==="radio"&&q(()=>{e.hasAttribute("name")||e.setAttribute("name",n)});let u=t.includes("change")||t.includes("lazy"),d=t.includes("blur"),f=t.includes("enter"),h=u||d||f,p;if(ve)p=()=>{};else if(h){let g=[],m=v=>c(Lt(e,t,v,l()));if(u&&g.push(qe(e,"change",t,m)),d&&(g.push(qe(e,"blur",t,m)),e.form)){let v=()=>m({target:e});e.form._x_pendingModelUpdates||(e.form._x_pendingModelUpdates=[]),e.form._x_pendingModelUpdates.push(v),s(()=>e.form._x_pendingModelUpdates.splice(e.form._x_pendingModelUpdates.indexOf(v),1))}f&&g.push(qe(e,"keydown",t,v=>{v.key==="Enter"&&m(v)})),p=()=>g.forEach(v=>v())}else{let g=e.tagName.toLowerCase()==="select"||["checkbox","radio"].includes(e.type)?"change":"input";p=qe(e,g,t,m=>{c(Lt(e,t,m,l()))})}if(t.includes("fill")&&([void 0,null,""].includes(l())||Xn(e)&&Array.isArray(l())||e.tagName.toLowerCase()==="select"&&e.multiple)&&c(Lt(e,t,{target:e},l())),e._x_removeModelListeners||(e._x_removeModelListeners={}),e._x_removeModelListeners.default=p,s(()=>e._x_removeModelListeners.default()),e.form){let g=qe(e.form,"reset",[],m=>{Jn(()=>e._x_model&&e._x_model.set(Lt(e,t,{target:e},l())))});s(()=>g())}e._x_model={get(){return l()},set(g){c(g)}},e._x_forceModelUpdate=g=>{g===void 0&&typeof n=="string"&&n.match(/\./)&&(g=""),window.fromModel=!0,q(()=>qs(e,"value",g)),delete window.fromModel},r(()=>{let g=l();t.includes("unintrusive")&&document.activeElement.isSameNode(e)||e._x_forceModelUpdate(g)})});function Lt(e,t,n,r){return q(()=>{if(n instanceof CustomEvent&&n.detail!==void 0)return n.detail!==null&&n.detail!==void 0?n.detail:n.target.value;if(Xn(e))if(Array.isArray(r)){let s=null;return t.includes("number")?s=yn(n.target.value):t.includes("boolean")?s=Bt(n.target.value):s=n.target.value,n.target.checked?r.includes(s)?r:r.concat([s]):r.filter(o=>!pc(o,s))}else return n.target.checked;else{if(e.tagName.toLowerCase()==="select"&&e.multiple)return t.includes("number")?Array.from(n.target.selectedOptions).map(s=>{let o=s.value||s.text;return yn(o)}):t.includes("boolean")?Array.from(n.target.selectedOptions).map(s=>{let o=s.value||s.text;return Bt(o)}):Array.from(n.target.selectedOptions).map(s=>s.value||s.text);{let s;return Us(e)?n.target.checked?s=n.target.value:s=r:s=n.target.value,t.includes("number")?yn(s):t.includes("boolean")?Bt(s):t.includes("trim")?s.trim():s}}})}function yn(e){let t=e?parseFloat(e):null;return hc(t)?t:e}function pc(e,t){return e==t}function hc(e){return!Array.isArray(e)&&!isNaN(e)}function ts(e){return e!==null&&typeof e=="object"&&typeof e.get=="function"&&typeof e.set=="function"}W("cloak",e=>queueMicrotask(()=>q(()=>e.removeAttribute(ze("cloak")))));Ms(()=>`[${ze("init")}]`);W("init",be((e,{expression:t},{evaluate:n})=>typeof t=="string"?!!t.trim()&&n(t,{},!1):n(t,{},!1)));W("text",(e,{expression:t},{effect:n,evaluateLater:r})=>{let s=r(t);n(()=>{s(o=>{q(()=>{e.textContent=o})})})});W("html",(e,{expression:t},{effect:n,evaluateLater:r})=>{let s=r(t);n(()=>{s(o=>{q(()=>{e.innerHTML=o,e._x_ignoreSelf=!0,ue(e),delete e._x_ignoreSelf})})})});Un(_s(":",Cs(ze("bind:"))));var vo=(e,{value:t,modifiers:n,expression:r,original:s},{effect:o,cleanup:i})=>{if(!t){let l={};vl(l),X(e,r)(u=>{Xs(e,u,s)},{scope:l});return}if(t==="key")return mc(e,r);if(e._x_inlineBindings&&e._x_inlineBindings[t]&&e._x_inlineBindings[t].extract)return;let a=X(e,r);o(()=>a(l=>{l===void 0&&typeof r=="string"&&r.match(/\./)&&(l=""),q(()=>qs(e,t,l,n))})),i(()=>{e._x_undoAddedClasses&&e._x_undoAddedClasses(),e._x_undoAddedStyles&&e._x_undoAddedStyles()})};vo.inline=(e,{value:t,modifiers:n,expression:r})=>{t&&(e._x_inlineBindings||(e._x_inlineBindings={}),e._x_inlineBindings[t]={expression:r,extract:!1})};W("bind",vo);function mc(e,t){e._x_keyExpression=t}Hs(()=>`[${ze("data")}]`);W("data",(e,{expression:t},{cleanup:n})=>{if(gc(e))return;t=t===""?"{}":t;let r={};ct(r,e);let s={};bl(s,r);let o=Ie(e,t,{scope:s});(o===void 0||o===!0)&&(o={}),ct(o,e);let i=Ve(o);Nn(i);let a=ft(e,i);i.init&&Ie(e,i.init),n(()=>{i.destroy&&Ie(e,i.destroy),a()})});Pt((e,t)=>{e._x_dataStack&&(t._x_dataStack=e._x_dataStack,t.setAttribute("data-has-alpine-state",!0))});function gc(e){return ve?$n?!0:e.hasAttribute("data-has-alpine-state"):!1}W("show",(e,{modifiers:t,expression:n},{effect:r})=>{let s=X(e,n);e._x_doHide||(e._x_doHide=()=>{q(()=>{e.style.setProperty("display","none",t.includes("important")?"important":void 0)})}),e._x_doShow||(e._x_doShow=()=>{q(()=>{e.style.length===1&&e.style.display==="none"?e.removeAttribute("style"):e.style.removeProperty("display")})});let o=()=>{e._x_doHide(),e._x_isShown=!1},i=()=>{e._x_doShow(),e._x_isShown=!0},a=()=>setTimeout(i),l=Tn(d=>d?i():o(),d=>{typeof e._x_toggleAndCascadeWithTransitions=="function"?e._x_toggleAndCascadeWithTransitions(e,d,i,o):d?a():o()}),c,u=!0;r(()=>s(d=>{!u&&d===c||(t.includes("immediate")&&(d?a():o()),l(d),c=d,u=!1)}))});W("for",(e,{expression:t},{effect:n,cleanup:r})=>{let s=yc(t),o=X(e,s.items),i=X(e,e._x_keyExpression||"index");e._x_prevKeys=[],e._x_lookup={},n(()=>vc(e,s,o,i)),r(()=>{Object.values(e._x_lookup).forEach(a=>q(()=>{We(a),a.remove()})),delete e._x_prevKeys,delete e._x_lookup})});function vc(e,t,n,r){let s=i=>typeof i=="object"&&!Array.isArray(i),o=e;n(i=>{bc(i)&&i>=0&&(i=Array.from(Array(i).keys(),m=>m+1)),i===void 0&&(i=[]);let a=e._x_lookup,l=e._x_prevKeys,c=[],u=[];if(s(i))i=Object.entries(i).map(([m,v])=>{let y=ns(t,v,m,i);r(x=>{u.includes(x)&&ee("Duplicate key on x-for",e),u.push(x)},{scope:{index:m,...y}}),c.push(y)});else for(let m=0;m<i.length;m++){let v=ns(t,i[m],m,i);r(y=>{u.includes(y)&&ee("Duplicate key on x-for",e),u.push(y)},{scope:{index:m,...v}}),c.push(v)}let d=[],f=[],h=[],p=[];for(let m=0;m<l.length;m++){let v=l[m];u.indexOf(v)===-1&&h.push(v)}l=l.filter(m=>!h.includes(m));let g="template";for(let m=0;m<u.length;m++){let v=u[m],y=l.indexOf(v);if(y===-1)l.splice(m,0,v),d.push([g,m]);else if(y!==m){let x=l.splice(m,1)[0],b=l.splice(y-1,1)[0];l.splice(m,0,b),l.splice(y,0,x),f.push([x,b])}else p.push(v);g=v}for(let m=0;m<h.length;m++){let v=h[m];v in a&&(q(()=>{We(a[v]),a[v].remove()}),delete a[v])}for(let m=0;m<f.length;m++){let[v,y]=f[m],x=a[v],b=a[y],j=document.createElement("div");q(()=>{b||ee('x-for ":key" is undefined or invalid',o,y,a),b.after(j),x.after(b),b._x_currentIfEl&&b.after(b._x_currentIfEl),j.before(x),x._x_currentIfEl&&x.after(x._x_currentIfEl),j.remove()}),b._x_refreshXForScope(c[u.indexOf(y)])}for(let m=0;m<d.length;m++){let[v,y]=d[m],x=v==="template"?o:a[v];x._x_currentIfEl&&(x=x._x_currentIfEl);let b=c[y],j=u[y],V=document.importNode(o.content,!0).firstElementChild,B=Ve(b);ft(V,B,o),V._x_refreshXForScope=U=>{Object.entries(U).forEach(([E,S])=>{B[E]=S})},q(()=>{x.after(V),be(()=>ue(V))()}),typeof j=="object"&&ee("x-for key cannot be an object, it must be a string or an integer",o),a[j]=V}for(let m=0;m<p.length;m++)a[p[m]]._x_refreshXForScope(c[u.indexOf(p[m])]);o._x_prevKeys=u})}function yc(e){let t=/,([^,\}\]]*)(?:,([^,\}\]]*))?$/,n=/^\s*\(|\)\s*$/g,r=/([\s\S]*?)\s+(?:in|of)\s+([\s\S]*)/,s=e.match(r);if(!s)return;let o={};o.items=s[2].trim();let i=s[1].replace(n,"").trim(),a=i.match(t);return a?(o.item=i.replace(t,"").trim(),o.index=a[1].trim(),a[2]&&(o.collection=a[2].trim())):o.item=i,o}function ns(e,t,n,r){let s={};return/^\[.*\]$/.test(e.item)&&Array.isArray(t)?e.item.replace("[","").replace("]","").split(",").map(i=>i.trim()).forEach((i,a)=>{s[i]=t[a]}):/^\{.*\}$/.test(e.item)&&!Array.isArray(t)&&typeof t=="object"?e.item.replace("{","").replace("}","").split(",").map(i=>i.trim()).forEach(i=>{s[i]=t[i]}):s[e.item]=t,e.index&&(s[e.index]=n),e.collection&&(s[e.collection]=r),s}function bc(e){return!Array.isArray(e)&&!isNaN(e)}function yo(){}yo.inline=(e,{expression:t},{cleanup:n})=>{let r=Dt(e);r._x_refs||(r._x_refs={}),r._x_refs[t]=e,n(()=>delete r._x_refs[t])};W("ref",yo);W("if",(e,{expression:t},{effect:n,cleanup:r})=>{e.tagName.toLowerCase()!=="template"&&ee("x-if can only be used on a <template> tag",e);let s=X(e,t),o=()=>{if(e._x_currentIfEl)return e._x_currentIfEl;let a=e.content.cloneNode(!0).firstElementChild;return ft(a,{},e),q(()=>{e.after(a),be(()=>ue(a))()}),e._x_currentIfEl=a,e._x_undoIf=()=>{q(()=>{We(a),a.remove()}),delete e._x_currentIfEl},a},i=()=>{e._x_undoIf&&(e._x_undoIf(),delete e._x_undoIf)};n(()=>s(a=>{a?o():i()})),r(()=>e._x_undoIf&&e._x_undoIf())});W("id",(e,{expression:t},{evaluate:n})=>{n(t).forEach(s=>oc(e,s))});Pt((e,t)=>{e._x_ids&&(t._x_ids=e._x_ids)});Un(_s("@",Cs(ze("on:"))));W("on",be((e,{value:t,modifiers:n,expression:r},{cleanup:s})=>{let o=r?X(e,r):()=>{};e.tagName.toLowerCase()==="template"&&(e._x_forwardEvents||(e._x_forwardEvents=[]),e._x_forwardEvents.includes(t)||e._x_forwardEvents.push(t));let i=qe(e,t,n,a=>{o(()=>{},{scope:{$event:a},params:[a]})});s(()=>i())}));Vt("Collapse","collapse","collapse");Vt("Intersect","intersect","intersect");Vt("Focus","trap","focus");Vt("Mask","mask","mask");function Vt(e,t,n){W(t,r=>ee(`You can't use [x-${t}] without first installing the "${e}" plugin here: https://alpinejs.dev/plugins/${n}`,r))}Je.setEvaluator(xs);Je.setRawEvaluator(La);Je.setReactivityEngine({reactive:nr,effect:Al,release:$l,raw:O});var xc=Je,fe=xc;var Ec=function(){"use strict";let htmx={onLoad:null,process:null,on:null,off:null,trigger:null,ajax:null,find:null,findAll:null,closest:null,values:function(e,t){return getInputValues(e,t||"post").values},remove:null,addClass:null,removeClass:null,toggleClass:null,takeClass:null,swap:null,defineExtension:null,removeExtension:null,logAll:null,logNone:null,logger:null,config:{historyEnabled:!0,historyCacheSize:10,refreshOnHistoryMiss:!1,defaultSwapStyle:"innerHTML",defaultSwapDelay:0,defaultSettleDelay:20,includeIndicatorStyles:!0,indicatorClass:"htmx-indicator",requestClass:"htmx-request",addedClass:"htmx-added",settlingClass:"htmx-settling",swappingClass:"htmx-swapping",allowEval:!0,allowScriptTags:!0,inlineScriptNonce:"",inlineStyleNonce:"",attributesToSettle:["class","style","width","height"],withCredentials:!1,timeout:0,wsReconnectDelay:"full-jitter",wsBinaryType:"blob",disableSelector:"[hx-disable], [data-hx-disable]",scrollBehavior:"instant",defaultFocusScroll:!1,getCacheBusterParam:!1,globalViewTransitions:!1,methodsThatUseUrlParams:["get","delete"],selfRequestsOnly:!0,ignoreTitle:!1,scrollIntoViewOnBoost:!0,triggerSpecsCache:null,disableInheritance:!1,responseHandling:[{code:"204",swap:!1},{code:"[23]..",swap:!0},{code:"[45]..",swap:!1,error:!0}],allowNestedOobSwaps:!0,historyRestoreAsHxRequest:!0,reportValidityOfForms:!1},parseInterval:null,location,_:null,version:"2.0.8"};htmx.onLoad=onLoadHelper,htmx.process=processNode,htmx.on=addEventListenerImpl,htmx.off=removeEventListenerImpl,htmx.trigger=triggerEvent,htmx.ajax=ajaxHelper,htmx.find=find,htmx.findAll=findAll,htmx.closest=closest,htmx.remove=removeElement,htmx.addClass=addClassToElement,htmx.removeClass=removeClassFromElement,htmx.toggleClass=toggleClassOnElement,htmx.takeClass=takeClassForElement,htmx.swap=swap,htmx.defineExtension=defineExtension,htmx.removeExtension=removeExtension,htmx.logAll=logAll,htmx.logNone=logNone,htmx.parseInterval=parseInterval,htmx._=internalEval;let internalAPI={addTriggerHandler,bodyContains,canAccessLocalStorage,findThisElement,filterValues,swap,hasAttribute,getAttributeValue,getClosestAttributeValue,getClosestMatch,getExpressionVars,getHeaders,getInputValues,getInternalData,getSwapSpecification,getTriggerSpecs,getTarget,makeFragment,mergeObjects,makeSettleInfo,oobSwap,querySelectorExt,settleImmediately,shouldCancel,triggerEvent,triggerErrorEvent,withExtensions},VERBS=["get","post","put","delete","patch"],VERB_SELECTOR=VERBS.map(function(e){return"[hx-"+e+"], [data-hx-"+e+"]"}).join(", ");function parseInterval(e){if(e==null)return;let t=NaN;return e.slice(-2)=="ms"?t=parseFloat(e.slice(0,-2)):e.slice(-1)=="s"?t=parseFloat(e.slice(0,-1))*1e3:e.slice(-1)=="m"?t=parseFloat(e.slice(0,-1))*1e3*60:t=parseFloat(e),isNaN(t)?void 0:t}function getRawAttribute(e,t){return e instanceof Element&&e.getAttribute(t)}function hasAttribute(e,t){return!!e.hasAttribute&&(e.hasAttribute(t)||e.hasAttribute("data-"+t))}function getAttributeValue(e,t){return getRawAttribute(e,t)||getRawAttribute(e,"data-"+t)}function parentElt(e){let t=e.parentElement;return!t&&e.parentNode instanceof ShadowRoot?e.parentNode:t}function getDocument(){return document}function getRootNode(e,t){return e.getRootNode?e.getRootNode({composed:t}):getDocument()}function getClosestMatch(e,t){for(;e&&!t(e);)e=parentElt(e);return e||null}function getAttributeValueWithDisinheritance(e,t,n){let r=getAttributeValue(t,n),s=getAttributeValue(t,"hx-disinherit");var o=getAttributeValue(t,"hx-inherit");if(e!==t){if(htmx.config.disableInheritance)return o&&(o==="*"||o.split(" ").indexOf(n)>=0)?r:null;if(s&&(s==="*"||s.split(" ").indexOf(n)>=0))return"unset"}return r}function getClosestAttributeValue(e,t){let n=null;if(getClosestMatch(e,function(r){return!!(n=getAttributeValueWithDisinheritance(e,asElement(r),t))}),n!=="unset")return n}function matches(e,t){return e instanceof Element&&e.matches(t)}function getStartTag(e){let n=/<([a-z][^\/\0>\x20\t\r\n\f]*)/i.exec(e);return n?n[1].toLowerCase():""}function parseHTML(e){return"parseHTMLUnsafe"in Document?Document.parseHTMLUnsafe(e):new DOMParser().parseFromString(e,"text/html")}function takeChildrenFor(e,t){for(;t.childNodes.length>0;)e.append(t.childNodes[0])}function duplicateScript(e){let t=getDocument().createElement("script");return forEach(e.attributes,function(n){t.setAttribute(n.name,n.value)}),t.textContent=e.textContent,t.async=!1,htmx.config.inlineScriptNonce&&(t.nonce=htmx.config.inlineScriptNonce),t}function isJavaScriptScriptNode(e){return e.matches("script")&&(e.type==="text/javascript"||e.type==="module"||e.type==="")}function normalizeScriptTags(e){Array.from(e.querySelectorAll("script")).forEach(t=>{if(isJavaScriptScriptNode(t)){let n=duplicateScript(t),r=t.parentNode;try{r.insertBefore(n,t)}catch(s){logError(s)}finally{t.remove()}}})}function makeFragment(e){let t=e.replace(/<head(\s[^>]*)?>[\s\S]*?<\/head>/i,""),n=getStartTag(t),r;if(n==="html"){r=new DocumentFragment;let o=parseHTML(e);takeChildrenFor(r,o.body),r.title=o.title}else if(n==="body"){r=new DocumentFragment;let o=parseHTML(t);takeChildrenFor(r,o.body),r.title=o.title}else{let o=parseHTML('<body><template class="internal-htmx-wrapper">'+t+"</template></body>");r=o.querySelector("template").content,r.title=o.title;var s=r.querySelector("title");s&&s.parentNode===r&&(s.remove(),r.title=s.innerText)}return r&&(htmx.config.allowScriptTags?normalizeScriptTags(r):r.querySelectorAll("script").forEach(o=>o.remove())),r}function maybeCall(e){e&&e()}function isType(e,t){return Object.prototype.toString.call(e)==="[object "+t+"]"}function isFunction(e){return typeof e=="function"}function isRawObject(e){return isType(e,"Object")}function getInternalData(e){let t="htmx-internal-data",n=e[t];return n||(n=e[t]={}),n}function toArray(e){let t=[];if(e)for(let n=0;n<e.length;n++)t.push(e[n]);return t}function forEach(e,t){if(e)for(let n=0;n<e.length;n++)t(e[n])}function isScrolledIntoView(e){let t=e.getBoundingClientRect(),n=t.top,r=t.bottom;return n<window.innerHeight&&r>=0}function bodyContains(e){return e.getRootNode({composed:!0})===document}function splitOnWhitespace(e){return e.trim().split(/\s+/)}function mergeObjects(e,t){for(let n in t)t.hasOwnProperty(n)&&(e[n]=t[n]);return e}function parseJSON(e){try{return JSON.parse(e)}catch(t){return logError(t),null}}function canAccessLocalStorage(){let e="htmx:sessionStorageTest";try{return sessionStorage.setItem(e,e),sessionStorage.removeItem(e),!0}catch{return!1}}function normalizePath(e){let t=new URL(e,"http://x");return t&&(e=t.pathname+t.search),e!="/"&&(e=e.replace(/\/+$/,"")),e}function internalEval(str){return maybeEval(getDocument().body,function(){return eval(str)})}function onLoadHelper(e){return htmx.on("htmx:load",function(n){e(n.detail.elt)})}function logAll(){htmx.logger=function(e,t,n){console&&console.log(t,e,n)}}function logNone(){htmx.logger=null}function find(e,t){return typeof e!="string"?e.querySelector(t):find(getDocument(),e)}function findAll(e,t){return typeof e!="string"?e.querySelectorAll(t):findAll(getDocument(),e)}function getWindow(){return window}function removeElement(e,t){e=resolveTarget(e),t?getWindow().setTimeout(function(){removeElement(e),e=null},t):parentElt(e).removeChild(e)}function asElement(e){return e instanceof Element?e:null}function asHtmlElement(e){return e instanceof HTMLElement?e:null}function asString(e){return typeof e=="string"?e:null}function asParentNode(e){return e instanceof Element||e instanceof Document||e instanceof DocumentFragment?e:null}function addClassToElement(e,t,n){e=asElement(resolveTarget(e)),e&&(n?getWindow().setTimeout(function(){addClassToElement(e,t),e=null},n):e.classList&&e.classList.add(t))}function removeClassFromElement(e,t,n){let r=asElement(resolveTarget(e));r&&(n?getWindow().setTimeout(function(){removeClassFromElement(r,t),r=null},n):r.classList&&(r.classList.remove(t),r.classList.length===0&&r.removeAttribute("class")))}function toggleClassOnElement(e,t){e=resolveTarget(e),e.classList.toggle(t)}function takeClassForElement(e,t){e=resolveTarget(e),forEach(e.parentElement.children,function(n){removeClassFromElement(n,t)}),addClassToElement(asElement(e),t)}function closest(e,t){return e=asElement(resolveTarget(e)),e?e.closest(t):null}function startsWith(e,t){return e.substring(0,t.length)===t}function endsWith(e,t){return e.substring(e.length-t.length)===t}function normalizeSelector(e){let t=e.trim();return startsWith(t,"<")&&endsWith(t,"/>")?t.substring(1,t.length-2):t}function querySelectorAllExt(e,t,n){if(t.indexOf("global ")===0)return querySelectorAllExt(e,t.slice(7),!0);e=resolveTarget(e);let r=[];{let i=0,a=0;for(let l=0;l<t.length;l++){let c=t[l];if(c===","&&i===0){r.push(t.substring(a,l)),a=l+1;continue}c==="<"?i++:c==="/"&&l<t.length-1&&t[l+1]===">"&&i--}a<t.length&&r.push(t.substring(a))}let s=[],o=[];for(;r.length>0;){let i=normalizeSelector(r.shift()),a;i.indexOf("closest ")===0?a=closest(asElement(e),normalizeSelector(i.slice(8))):i.indexOf("find ")===0?a=find(asParentNode(e),normalizeSelector(i.slice(5))):i==="next"||i==="nextElementSibling"?a=asElement(e).nextElementSibling:i.indexOf("next ")===0?a=scanForwardQuery(e,normalizeSelector(i.slice(5)),!!n):i==="previous"||i==="previousElementSibling"?a=asElement(e).previousElementSibling:i.indexOf("previous ")===0?a=scanBackwardsQuery(e,normalizeSelector(i.slice(9)),!!n):i==="document"?a=document:i==="window"?a=window:i==="body"?a=document.body:i==="root"?a=getRootNode(e,!!n):i==="host"?a=e.getRootNode().host:o.push(i),a&&s.push(a)}if(o.length>0){let i=o.join(","),a=asParentNode(getRootNode(e,!!n));s.push(...toArray(a.querySelectorAll(i)))}return s}var scanForwardQuery=function(e,t,n){let r=asParentNode(getRootNode(e,n)).querySelectorAll(t);for(let s=0;s<r.length;s++){let o=r[s];if(o.compareDocumentPosition(e)===Node.DOCUMENT_POSITION_PRECEDING)return o}},scanBackwardsQuery=function(e,t,n){let r=asParentNode(getRootNode(e,n)).querySelectorAll(t);for(let s=r.length-1;s>=0;s--){let o=r[s];if(o.compareDocumentPosition(e)===Node.DOCUMENT_POSITION_FOLLOWING)return o}};function querySelectorExt(e,t){return typeof e!="string"?querySelectorAllExt(e,t)[0]:querySelectorAllExt(getDocument().body,e)[0]}function resolveTarget(e,t){return typeof e=="string"?find(asParentNode(t)||document,e):e}function processEventArgs(e,t,n,r){return isFunction(t)?{target:getDocument().body,event:asString(e),listener:t,options:n}:{target:resolveTarget(e),event:asString(t),listener:n,options:r}}function addEventListenerImpl(e,t,n,r){return ready(function(){let o=processEventArgs(e,t,n,r);o.target.addEventListener(o.event,o.listener,o.options)}),isFunction(t)?t:n}function removeEventListenerImpl(e,t,n){return ready(function(){let r=processEventArgs(e,t,n);r.target.removeEventListener(r.event,r.listener)}),isFunction(t)?t:n}let DUMMY_ELT=getDocument().createElement("output");function findAttributeTargets(e,t){let n=getClosestAttributeValue(e,t);if(n){if(n==="this")return[findThisElement(e,t)];{let r=querySelectorAllExt(e,n);if(/(^|,)(\s*)inherit(\s*)($|,)/.test(n)){let o=asElement(getClosestMatch(e,function(i){return i!==e&&hasAttribute(asElement(i),t)}));o&&r.push(...findAttributeTargets(o,t))}return r.length===0?(logError('The selector "'+n+'" on '+t+" returned no matches!"),[DUMMY_ELT]):r}}}function findThisElement(e,t){return asElement(getClosestMatch(e,function(n){return getAttributeValue(asElement(n),t)!=null}))}function getTarget(e){let t=getClosestAttributeValue(e,"hx-target");return t?t==="this"?findThisElement(e,"hx-target"):querySelectorExt(e,t):getInternalData(e).boosted?getDocument().body:e}function shouldSettleAttribute(e){return htmx.config.attributesToSettle.includes(e)}function cloneAttributes(e,t){forEach(Array.from(e.attributes),function(n){!t.hasAttribute(n.name)&&shouldSettleAttribute(n.name)&&e.removeAttribute(n.name)}),forEach(t.attributes,function(n){shouldSettleAttribute(n.name)&&e.setAttribute(n.name,n.value)})}function isInlineSwap(e,t){let n=getExtensions(t);for(let r=0;r<n.length;r++){let s=n[r];try{if(s.isInlineSwap(e))return!0}catch(o){logError(o)}}return e==="outerHTML"}function oobSwap(e,t,n,r){r=r||getDocument();let s="#"+CSS.escape(getRawAttribute(t,"id")),o="outerHTML";e==="true"||(e.indexOf(":")>0?(o=e.substring(0,e.indexOf(":")),s=e.substring(e.indexOf(":")+1)):o=e),t.removeAttribute("hx-swap-oob"),t.removeAttribute("data-hx-swap-oob");let i=querySelectorAllExt(r,s,!1);return i.length?(forEach(i,function(a){let l,c=t.cloneNode(!0);l=getDocument().createDocumentFragment(),l.appendChild(c),isInlineSwap(o,a)||(l=asParentNode(c));let u={shouldSwap:!0,target:a,fragment:l};triggerEvent(a,"htmx:oobBeforeSwap",u)&&(a=u.target,u.shouldSwap&&(handlePreservedElements(l),swapWithStyle(o,a,a,l,n),restorePreservedElements()),forEach(n.elts,function(d){triggerEvent(d,"htmx:oobAfterSwap",u)}))}),t.parentNode.removeChild(t)):(t.parentNode.removeChild(t),triggerErrorEvent(getDocument().body,"htmx:oobErrorNoTarget",{content:t})),e}function restorePreservedElements(){let e=find("#--htmx-preserve-pantry--");if(e){for(let t of[...e.children]){let n=find("#"+t.id);n.parentNode.moveBefore(t,n),n.remove()}e.remove()}}function handlePreservedElements(e){forEach(findAll(e,"[hx-preserve], [data-hx-preserve]"),function(t){let n=getAttributeValue(t,"id"),r=getDocument().getElementById(n);if(r!=null)if(t.moveBefore){let s=find("#--htmx-preserve-pantry--");s==null&&(getDocument().body.insertAdjacentHTML("afterend","<div id='--htmx-preserve-pantry--'></div>"),s=find("#--htmx-preserve-pantry--")),s.moveBefore(r,null)}else t.parentNode.replaceChild(r,t)})}function handleAttributes(e,t,n){forEach(t.querySelectorAll("[id]"),function(r){let s=getRawAttribute(r,"id");if(s&&s.length>0){let o=s.replace("'","\\'"),i=r.tagName.replace(":","\\:"),a=asParentNode(e),l=a&&a.querySelector(i+"[id='"+o+"']");if(l&&l!==a){let c=r.cloneNode();cloneAttributes(r,l),n.tasks.push(function(){cloneAttributes(r,c)})}}})}function makeAjaxLoadTask(e){return function(){removeClassFromElement(e,htmx.config.addedClass),processNode(asElement(e)),processFocus(asParentNode(e)),triggerEvent(e,"htmx:load")}}function processFocus(e){let t="[autofocus]",n=asHtmlElement(matches(e,t)?e:e.querySelector(t));n?.focus()}function insertNodesBefore(e,t,n,r){for(handleAttributes(e,n,r);n.childNodes.length>0;){let s=n.firstChild;addClassToElement(asElement(s),htmx.config.addedClass),e.insertBefore(s,t),s.nodeType!==Node.TEXT_NODE&&s.nodeType!==Node.COMMENT_NODE&&r.tasks.push(makeAjaxLoadTask(s))}}function stringHash(e,t){let n=0;for(;n<e.length;)t=(t<<5)-t+e.charCodeAt(n++)|0;return t}function attributeHash(e){let t=0;for(let n=0;n<e.attributes.length;n++){let r=e.attributes[n];r.value&&(t=stringHash(r.name,t),t=stringHash(r.value,t))}return t}function deInitOnHandlers(e){let t=getInternalData(e);if(t.onHandlers){for(let n=0;n<t.onHandlers.length;n++){let r=t.onHandlers[n];removeEventListenerImpl(e,r.event,r.listener)}delete t.onHandlers}}function deInitNode(e){let t=getInternalData(e);t.timeout&&clearTimeout(t.timeout),t.listenerInfos&&forEach(t.listenerInfos,function(n){n.on&&removeEventListenerImpl(n.on,n.trigger,n.listener)}),deInitOnHandlers(e),forEach(Object.keys(t),function(n){n!=="firstInitCompleted"&&delete t[n]})}function cleanUpElement(e){triggerEvent(e,"htmx:beforeCleanupElement"),deInitNode(e),forEach(e.children,function(t){cleanUpElement(t)})}function swapOuterHTML(e,t,n){if(e.tagName==="BODY")return swapInnerHTML(e,t,n);let r,s=e.previousSibling,o=parentElt(e);if(o){for(insertNodesBefore(o,e,t,n),s==null?r=o.firstChild:r=s.nextSibling,n.elts=n.elts.filter(function(i){return i!==e});r&&r!==e;)r instanceof Element&&n.elts.push(r),r=r.nextSibling;cleanUpElement(e),e.remove()}}function swapAfterBegin(e,t,n){return insertNodesBefore(e,e.firstChild,t,n)}function swapBeforeBegin(e,t,n){return insertNodesBefore(parentElt(e),e,t,n)}function swapBeforeEnd(e,t,n){return insertNodesBefore(e,null,t,n)}function swapAfterEnd(e,t,n){return insertNodesBefore(parentElt(e),e.nextSibling,t,n)}function swapDelete(e){cleanUpElement(e);let t=parentElt(e);if(t)return t.removeChild(e)}function swapInnerHTML(e,t,n){let r=e.firstChild;if(insertNodesBefore(e,r,t,n),r){for(;r.nextSibling;)cleanUpElement(r.nextSibling),e.removeChild(r.nextSibling);cleanUpElement(r),e.removeChild(r)}}function swapWithStyle(e,t,n,r,s){switch(e){case"none":return;case"outerHTML":swapOuterHTML(n,r,s);return;case"afterbegin":swapAfterBegin(n,r,s);return;case"beforebegin":swapBeforeBegin(n,r,s);return;case"beforeend":swapBeforeEnd(n,r,s);return;case"afterend":swapAfterEnd(n,r,s);return;case"delete":swapDelete(n);return;default:var o=getExtensions(t);for(let i=0;i<o.length;i++){let a=o[i];try{let l=a.handleSwap(e,n,r,s);if(l){if(Array.isArray(l))for(let c=0;c<l.length;c++){let u=l[c];u.nodeType!==Node.TEXT_NODE&&u.nodeType!==Node.COMMENT_NODE&&s.tasks.push(makeAjaxLoadTask(u))}return}}catch(l){logError(l)}}e==="innerHTML"?swapInnerHTML(n,r,s):swapWithStyle(htmx.config.defaultSwapStyle,t,n,r,s)}}function findAndSwapOobElements(e,t,n){var r=findAll(e,"[hx-swap-oob], [data-hx-swap-oob]");return forEach(r,function(s){if(htmx.config.allowNestedOobSwaps||s.parentElement===null){let o=getAttributeValue(s,"hx-swap-oob");o!=null&&oobSwap(o,s,t,n)}else s.removeAttribute("hx-swap-oob"),s.removeAttribute("data-hx-swap-oob")}),r.length>0}function swap(e,t,n,r){r||(r={});let s=null,o=null,i=function(){maybeCall(r.beforeSwapCallback),e=resolveTarget(e);let c=r.contextElement?getRootNode(r.contextElement,!1):getDocument(),u=document.activeElement,d={};d={elt:u,start:u?u.selectionStart:null,end:u?u.selectionEnd:null};let f=makeSettleInfo(e);if(n.swapStyle==="textContent")e.textContent=t;else{let p=makeFragment(t);if(f.title=r.title||p.title,r.historyRequest&&(p=p.querySelector("[hx-history-elt],[data-hx-history-elt]")||p),r.selectOOB){let g=r.selectOOB.split(",");for(let m=0;m<g.length;m++){let v=g[m].split(":",2),y=v[0].trim();y.indexOf("#")===0&&(y=y.substring(1));let x=v[1]||"true",b=p.querySelector("#"+y);b&&oobSwap(x,b,f,c)}}if(findAndSwapOobElements(p,f,c),forEach(findAll(p,"template"),function(g){g.content&&findAndSwapOobElements(g.content,f,c)&&g.remove()}),r.select){let g=getDocument().createDocumentFragment();forEach(p.querySelectorAll(r.select),function(m){g.appendChild(m)}),p=g}handlePreservedElements(p),swapWithStyle(n.swapStyle,r.contextElement,e,p,f),restorePreservedElements()}if(d.elt&&!bodyContains(d.elt)&&getRawAttribute(d.elt,"id")){let p=document.getElementById(getRawAttribute(d.elt,"id")),g={preventScroll:n.focusScroll!==void 0?!n.focusScroll:!htmx.config.defaultFocusScroll};if(p){if(d.start&&p.setSelectionRange)try{p.setSelectionRange(d.start,d.end)}catch{}p.focus(g)}}e.classList.remove(htmx.config.swappingClass),forEach(f.elts,function(p){p.classList&&p.classList.add(htmx.config.settlingClass),triggerEvent(p,"htmx:afterSwap",r.eventInfo)}),maybeCall(r.afterSwapCallback),n.ignoreTitle||handleTitle(f.title);let h=function(){if(forEach(f.tasks,function(p){p.call()}),forEach(f.elts,function(p){p.classList&&p.classList.remove(htmx.config.settlingClass),triggerEvent(p,"htmx:afterSettle",r.eventInfo)}),r.anchor){let p=asElement(resolveTarget("#"+r.anchor));p&&p.scrollIntoView({block:"start",behavior:"auto"})}updateScrollState(f.elts,n),maybeCall(r.afterSettleCallback),maybeCall(s)};n.settleDelay>0?getWindow().setTimeout(h,n.settleDelay):h()},a=htmx.config.globalViewTransitions;n.hasOwnProperty("transition")&&(a=n.transition);let l=r.contextElement||getDocument();if(a&&triggerEvent(l,"htmx:beforeTransition",r.eventInfo)&&typeof Promise<"u"&&document.startViewTransition){let c=new Promise(function(d,f){s=d,o=f}),u=i;i=function(){document.startViewTransition(function(){return u(),c})}}try{n?.swapDelay&&n.swapDelay>0?getWindow().setTimeout(i,n.swapDelay):i()}catch(c){throw triggerErrorEvent(l,"htmx:swapError",r.eventInfo),maybeCall(o),c}}function handleTriggerHeader(e,t,n){let r=e.getResponseHeader(t);if(r.indexOf("{")===0){let s=parseJSON(r);for(let o in s)if(s.hasOwnProperty(o)){let i=s[o];isRawObject(i)?n=i.target!==void 0?i.target:n:i={value:i},triggerEvent(n,o,i)}}else{let s=r.split(",");for(let o=0;o<s.length;o++)triggerEvent(n,s[o].trim(),[])}}let WHITESPACE=/\s/,WHITESPACE_OR_COMMA=/[\s,]/,SYMBOL_START=/[_$a-zA-Z]/,SYMBOL_CONT=/[_$a-zA-Z0-9]/,STRINGISH_START=['"',"'","/"],NOT_WHITESPACE=/[^\s]/,COMBINED_SELECTOR_START=/[{(]/,COMBINED_SELECTOR_END=/[})]/;function tokenizeString(e){let t=[],n=0;for(;n<e.length;){if(SYMBOL_START.exec(e.charAt(n))){for(var r=n;SYMBOL_CONT.exec(e.charAt(n+1));)n++;t.push(e.substring(r,n+1))}else if(STRINGISH_START.indexOf(e.charAt(n))!==-1){let s=e.charAt(n);var r=n;for(n++;n<e.length&&e.charAt(n)!==s;)e.charAt(n)==="\\"&&n++,n++;t.push(e.substring(r,n+1))}else{let s=e.charAt(n);t.push(s)}n++}return t}function isPossibleRelativeReference(e,t,n){return SYMBOL_START.exec(e.charAt(0))&&e!=="true"&&e!=="false"&&e!=="this"&&e!==n&&t!=="."}function maybeGenerateConditional(e,t,n){if(t[0]==="["){t.shift();let r=1,s=" return (function("+n+"){ return (",o=null;for(;t.length>0;){let i=t[0];if(i==="]"){if(r--,r===0){o===null&&(s=s+"true"),t.shift(),s+=")})";try{let a=maybeEval(e,function(){return Function(s)()},function(){return!0});return a.source=s,a}catch(a){return triggerErrorEvent(getDocument().body,"htmx:syntax:error",{error:a,source:s}),null}}}else i==="["&&r++;isPossibleRelativeReference(i,o,n)?s+="(("+n+"."+i+") ? ("+n+"."+i+") : (window."+i+"))":s=s+i,o=t.shift()}}}function consumeUntil(e,t){let n="";for(;e.length>0&&!t.test(e[0]);)n+=e.shift();return n}function consumeCSSSelector(e){let t;return e.length>0&&COMBINED_SELECTOR_START.test(e[0])?(e.shift(),t=consumeUntil(e,COMBINED_SELECTOR_END).trim(),e.shift()):t=consumeUntil(e,WHITESPACE_OR_COMMA),t}let INPUT_SELECTOR="input, textarea, select";function parseAndCacheTrigger(e,t,n){let r=[],s=tokenizeString(t);do{consumeUntil(s,NOT_WHITESPACE);let a=s.length,l=consumeUntil(s,/[,\[\s]/);if(l!=="")if(l==="every"){let c={trigger:"every"};consumeUntil(s,NOT_WHITESPACE),c.pollInterval=parseInterval(consumeUntil(s,/[,\[\s]/)),consumeUntil(s,NOT_WHITESPACE);var o=maybeGenerateConditional(e,s,"event");o&&(c.eventFilter=o),r.push(c)}else{let c={trigger:l};var o=maybeGenerateConditional(e,s,"event");for(o&&(c.eventFilter=o),consumeUntil(s,NOT_WHITESPACE);s.length>0&&s[0]!==",";){let d=s.shift();if(d==="changed")c.changed=!0;else if(d==="once")c.once=!0;else if(d==="consume")c.consume=!0;else if(d==="delay"&&s[0]===":")s.shift(),c.delay=parseInterval(consumeUntil(s,WHITESPACE_OR_COMMA));else if(d==="from"&&s[0]===":"){if(s.shift(),COMBINED_SELECTOR_START.test(s[0]))var i=consumeCSSSelector(s);else{var i=consumeUntil(s,WHITESPACE_OR_COMMA);if(i==="closest"||i==="find"||i==="next"||i==="previous"){s.shift();let h=consumeCSSSelector(s);h.length>0&&(i+=" "+h)}}c.from=i}else d==="target"&&s[0]===":"?(s.shift(),c.target=consumeCSSSelector(s)):d==="throttle"&&s[0]===":"?(s.shift(),c.throttle=parseInterval(consumeUntil(s,WHITESPACE_OR_COMMA))):d==="queue"&&s[0]===":"?(s.shift(),c.queue=consumeUntil(s,WHITESPACE_OR_COMMA)):d==="root"&&s[0]===":"?(s.shift(),c[d]=consumeCSSSelector(s)):d==="threshold"&&s[0]===":"?(s.shift(),c[d]=consumeUntil(s,WHITESPACE_OR_COMMA)):triggerErrorEvent(e,"htmx:syntax:error",{token:s.shift()});consumeUntil(s,NOT_WHITESPACE)}r.push(c)}s.length===a&&triggerErrorEvent(e,"htmx:syntax:error",{token:s.shift()}),consumeUntil(s,NOT_WHITESPACE)}while(s[0]===","&&s.shift());return n&&(n[t]=r),r}function getTriggerSpecs(e){let t=getAttributeValue(e,"hx-trigger"),n=[];if(t){let r=htmx.config.triggerSpecsCache;n=r&&r[t]||parseAndCacheTrigger(e,t,r)}return n.length>0?n:matches(e,"form")?[{trigger:"submit"}]:matches(e,'input[type="button"], input[type="submit"]')?[{trigger:"click"}]:matches(e,INPUT_SELECTOR)?[{trigger:"change"}]:[{trigger:"click"}]}function cancelPolling(e){getInternalData(e).cancelled=!0}function processPolling(e,t,n){let r=getInternalData(e);r.timeout=getWindow().setTimeout(function(){bodyContains(e)&&r.cancelled!==!0&&(maybeFilterEvent(n,e,makeEvent("hx:poll:trigger",{triggerSpec:n,target:e}))||t(e),processPolling(e,t,n))},n.pollInterval)}function isLocalLink(e){return location.hostname===e.hostname&&getRawAttribute(e,"href")&&getRawAttribute(e,"href").indexOf("#")!==0}function eltIsDisabled(e){return closest(e,htmx.config.disableSelector)}function boostElement(e,t,n){if(e instanceof HTMLAnchorElement&&isLocalLink(e)&&(e.target===""||e.target==="_self")||e.tagName==="FORM"&&String(getRawAttribute(e,"method")).toLowerCase()!=="dialog"){t.boosted=!0;let r,s;if(e.tagName==="A")r="get",s=getRawAttribute(e,"href");else{let o=getRawAttribute(e,"method");r=o?o.toLowerCase():"get",s=getRawAttribute(e,"action"),(s==null||s==="")&&(s=location.href),r==="get"&&s.includes("?")&&(s=s.replace(/\?[^#]+/,""))}n.forEach(function(o){addEventListener(e,function(i,a){let l=asElement(i);if(eltIsDisabled(l)){cleanUpElement(l);return}issueAjaxRequest(r,s,l,a)},t,o,!0)})}}function shouldCancel(e,t){if(e.type==="submit"&&t.tagName==="FORM")return!0;if(e.type==="click"){let n=t.closest('input[type="submit"], button');if(n&&n.form&&n.type==="submit")return!0;let r=t.closest("a"),s=/^#.+/;if(r&&r.href&&!s.test(r.getAttribute("href")))return!0}return!1}function ignoreBoostedAnchorCtrlClick(e,t){return getInternalData(e).boosted&&e instanceof HTMLAnchorElement&&t.type==="click"&&(t.ctrlKey||t.metaKey)}function maybeFilterEvent(e,t,n){let r=e.eventFilter;if(r)try{return r.call(t,n)!==!0}catch(s){let o=r.source;return triggerErrorEvent(getDocument().body,"htmx:eventFilter:error",{error:s,source:o}),!0}return!1}function addEventListener(e,t,n,r,s){let o=getInternalData(e),i;r.from?i=querySelectorAllExt(e,r.from):i=[e],r.changed&&("lastValue"in o||(o.lastValue=new WeakMap),i.forEach(function(a){o.lastValue.has(r)||o.lastValue.set(r,new WeakMap),o.lastValue.get(r).set(a,a.value)})),forEach(i,function(a){let l=function(c){if(!bodyContains(e)){a.removeEventListener(r.trigger,l);return}if(ignoreBoostedAnchorCtrlClick(e,c)||((s||shouldCancel(c,a))&&c.preventDefault(),maybeFilterEvent(r,e,c)))return;let u=getInternalData(c);if(u.triggerSpec=r,u.handledFor==null&&(u.handledFor=[]),u.handledFor.indexOf(e)<0){if(u.handledFor.push(e),r.consume&&c.stopPropagation(),r.target&&c.target&&!matches(asElement(c.target),r.target))return;if(r.once){if(o.triggeredOnce)return;o.triggeredOnce=!0}if(r.changed){let d=c.target,f=d.value,h=o.lastValue.get(r);if(h.has(d)&&h.get(d)===f)return;h.set(d,f)}if(o.delayed&&clearTimeout(o.delayed),o.throttle)return;r.throttle>0?o.throttle||(triggerEvent(e,"htmx:trigger"),t(e,c),o.throttle=getWindow().setTimeout(function(){o.throttle=null},r.throttle)):r.delay>0?o.delayed=getWindow().setTimeout(function(){triggerEvent(e,"htmx:trigger"),t(e,c)},r.delay):(triggerEvent(e,"htmx:trigger"),t(e,c))}};n.listenerInfos==null&&(n.listenerInfos=[]),n.listenerInfos.push({trigger:r.trigger,listener:l,on:a}),a.addEventListener(r.trigger,l)})}let windowIsScrolling=!1,scrollHandler=null;function initScrollHandler(){scrollHandler||(scrollHandler=function(){windowIsScrolling=!0},window.addEventListener("scroll",scrollHandler),window.addEventListener("resize",scrollHandler),setInterval(function(){windowIsScrolling&&(windowIsScrolling=!1,forEach(getDocument().querySelectorAll("[hx-trigger*='revealed'],[data-hx-trigger*='revealed']"),function(e){maybeReveal(e)}))},200))}function maybeReveal(e){!hasAttribute(e,"data-hx-revealed")&&isScrolledIntoView(e)&&(e.setAttribute("data-hx-revealed","true"),getInternalData(e).initHash?triggerEvent(e,"revealed"):e.addEventListener("htmx:afterProcessNode",function(){triggerEvent(e,"revealed")},{once:!0}))}function loadImmediately(e,t,n,r){let s=function(){n.loaded||(n.loaded=!0,triggerEvent(e,"htmx:trigger"),t(e))};r>0?getWindow().setTimeout(s,r):s()}function processVerbs(e,t,n){let r=!1;return forEach(VERBS,function(s){if(hasAttribute(e,"hx-"+s)){let o=getAttributeValue(e,"hx-"+s);r=!0,t.path=o,t.verb=s,n.forEach(function(i){addTriggerHandler(e,i,t,function(a,l){let c=asElement(a);if(eltIsDisabled(c)){cleanUpElement(c);return}issueAjaxRequest(s,o,c,l)})})}}),r}function addTriggerHandler(e,t,n,r){if(t.trigger==="revealed")initScrollHandler(),addEventListener(e,r,n,t),maybeReveal(asElement(e));else if(t.trigger==="intersect"){let s={};t.root&&(s.root=querySelectorExt(e,t.root)),t.threshold&&(s.threshold=parseFloat(t.threshold)),new IntersectionObserver(function(i){for(let a=0;a<i.length;a++)if(i[a].isIntersecting){triggerEvent(e,"intersect");break}},s).observe(asElement(e)),addEventListener(asElement(e),r,n,t)}else!n.firstInitCompleted&&t.trigger==="load"?maybeFilterEvent(t,e,makeEvent("load",{elt:e}))||loadImmediately(asElement(e),r,n,t.delay):t.pollInterval>0?(n.polling=!0,processPolling(asElement(e),r,t)):addEventListener(e,r,n,t)}function shouldProcessHxOn(e){let t=asElement(e);if(!t)return!1;let n=t.attributes;for(let r=0;r<n.length;r++){let s=n[r].name;if(startsWith(s,"hx-on:")||startsWith(s,"data-hx-on:")||startsWith(s,"hx-on-")||startsWith(s,"data-hx-on-"))return!0}return!1}let HX_ON_QUERY=new XPathEvaluator().createExpression('.//*[@*[ starts-with(name(), "hx-on:") or starts-with(name(), "data-hx-on:") or starts-with(name(), "hx-on-") or starts-with(name(), "data-hx-on-") ]]');function processHXOnRoot(e,t){shouldProcessHxOn(e)&&t.push(asElement(e));let n=HX_ON_QUERY.evaluate(e),r=null;for(;r=n.iterateNext();)t.push(asElement(r))}function findHxOnWildcardElements(e){let t=[];if(e instanceof DocumentFragment)for(let n of e.childNodes)processHXOnRoot(n,t);else processHXOnRoot(e,t);return t}function findElementsToProcess(e){if(e.querySelectorAll){let n=", [hx-boost] a, [data-hx-boost] a, a[hx-boost], a[data-hx-boost]",r=[];for(let o in extensions){let i=extensions[o];if(i.getSelectors){var t=i.getSelectors();t&&r.push(t)}}return e.querySelectorAll(VERB_SELECTOR+n+", form, [type='submit'], [hx-ext], [data-hx-ext], [hx-trigger], [data-hx-trigger]"+r.flat().map(o=>", "+o).join(""))}else return[]}function maybeSetLastButtonClicked(e){let t=getTargetButton(e.target),n=getRelatedFormData(e);n&&(n.lastButtonClicked=t)}function maybeUnsetLastButtonClicked(e){let t=getRelatedFormData(e);t&&(t.lastButtonClicked=null)}function getTargetButton(e){return closest(asElement(e),"button, input[type='submit']")}function getRelatedForm(e){return e.form||closest(e,"form")}function getRelatedFormData(e){let t=getTargetButton(e.target);if(!t)return;let n=getRelatedForm(t);if(n)return getInternalData(n)}function initButtonTracking(e){e.addEventListener("click",maybeSetLastButtonClicked),e.addEventListener("focusin",maybeSetLastButtonClicked),e.addEventListener("focusout",maybeUnsetLastButtonClicked)}function addHxOnEventHandler(e,t,n){let r=getInternalData(e);Array.isArray(r.onHandlers)||(r.onHandlers=[]);let s,o=function(i){maybeEval(e,function(){eltIsDisabled(e)||(s||(s=new Function("event",n)),s.call(e,i))})};e.addEventListener(t,o),r.onHandlers.push({event:t,listener:o})}function processHxOnWildcard(e){deInitOnHandlers(e);for(let t=0;t<e.attributes.length;t++){let n=e.attributes[t].name,r=e.attributes[t].value;if(startsWith(n,"hx-on")||startsWith(n,"data-hx-on")){let s=n.indexOf("-on")+3,o=n.slice(s,s+1);if(o==="-"||o===":"){let i=n.slice(s+1);startsWith(i,":")?i="htmx"+i:startsWith(i,"-")?i="htmx:"+i.slice(1):startsWith(i,"htmx-")&&(i="htmx:"+i.slice(5)),addHxOnEventHandler(e,i,r)}}}}function initNode(e){triggerEvent(e,"htmx:beforeProcessNode");let t=getInternalData(e),n=getTriggerSpecs(e);processVerbs(e,t,n)||(getClosestAttributeValue(e,"hx-boost")==="true"?boostElement(e,t,n):hasAttribute(e,"hx-trigger")&&n.forEach(function(s){addTriggerHandler(e,s,t,function(){})})),(e.tagName==="FORM"||getRawAttribute(e,"type")==="submit"&&hasAttribute(e,"form"))&&initButtonTracking(e),t.firstInitCompleted=!0,triggerEvent(e,"htmx:afterProcessNode")}function maybeDeInitAndHash(e){if(!(e instanceof Element))return!1;let t=getInternalData(e),n=attributeHash(e);return t.initHash!==n?(deInitNode(e),t.initHash=n,!0):!1}function processNode(e){if(e=resolveTarget(e),eltIsDisabled(e)){cleanUpElement(e);return}let t=[];maybeDeInitAndHash(e)&&t.push(e),forEach(findElementsToProcess(e),function(n){if(eltIsDisabled(n)){cleanUpElement(n);return}maybeDeInitAndHash(n)&&t.push(n)}),forEach(findHxOnWildcardElements(e),processHxOnWildcard),forEach(t,initNode)}function kebabEventName(e){return e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase()}function makeEvent(e,t){return new CustomEvent(e,{bubbles:!0,cancelable:!0,composed:!0,detail:t})}function triggerErrorEvent(e,t,n){triggerEvent(e,t,mergeObjects({error:t},n))}function ignoreEventForLogging(e){return e==="htmx:afterProcessNode"}function withExtensions(e,t,n){forEach(getExtensions(e,[],n),function(r){try{t(r)}catch(s){logError(s)}})}function logError(e){console.error(e)}function triggerEvent(e,t,n){e=resolveTarget(e),n==null&&(n={}),n.elt=e;let r=makeEvent(t,n);htmx.logger&&!ignoreEventForLogging(t)&&htmx.logger(e,t,n),n.error&&(logError(n.error),triggerEvent(e,"htmx:error",{errorInfo:n}));let s=e.dispatchEvent(r),o=kebabEventName(t);if(s&&o!==t){let i=makeEvent(o,r.detail);s=s&&e.dispatchEvent(i)}return withExtensions(asElement(e),function(i){s=s&&i.onEvent(t,r)!==!1&&!r.defaultPrevented}),s}let currentPathForHistory;function setCurrentPathForHistory(e){currentPathForHistory=e,canAccessLocalStorage()&&sessionStorage.setItem("htmx-current-path-for-history",e)}setCurrentPathForHistory(location.pathname+location.search);function getHistoryElement(){return getDocument().querySelector("[hx-history-elt],[data-hx-history-elt]")||getDocument().body}function saveToHistoryCache(e,t){if(!canAccessLocalStorage())return;let n=cleanInnerHtmlForHistory(t),r=getDocument().title,s=window.scrollY;if(htmx.config.historyCacheSize<=0){sessionStorage.removeItem("htmx-history-cache");return}e=normalizePath(e);let o=parseJSON(sessionStorage.getItem("htmx-history-cache"))||[];for(let a=0;a<o.length;a++)if(o[a].url===e){o.splice(a,1);break}let i={url:e,content:n,title:r,scroll:s};for(triggerEvent(getDocument().body,"htmx:historyItemCreated",{item:i,cache:o}),o.push(i);o.length>htmx.config.historyCacheSize;)o.shift();for(;o.length>0;)try{sessionStorage.setItem("htmx-history-cache",JSON.stringify(o));break}catch(a){triggerErrorEvent(getDocument().body,"htmx:historyCacheError",{cause:a,cache:o}),o.shift()}}function getCachedHistory(e){if(!canAccessLocalStorage())return null;e=normalizePath(e);let t=parseJSON(sessionStorage.getItem("htmx-history-cache"))||[];for(let n=0;n<t.length;n++)if(t[n].url===e)return t[n];return null}function cleanInnerHtmlForHistory(e){let t=htmx.config.requestClass,n=e.cloneNode(!0);return forEach(findAll(n,"."+t),function(r){removeClassFromElement(r,t)}),forEach(findAll(n,"[data-disabled-by-htmx]"),function(r){r.removeAttribute("disabled")}),n.innerHTML}function saveCurrentPageToHistory(){let e=getHistoryElement(),t=currentPathForHistory;canAccessLocalStorage()&&(t=sessionStorage.getItem("htmx-current-path-for-history")),t=t||location.pathname+location.search,getDocument().querySelector('[hx-history="false" i],[data-hx-history="false" i]')||(triggerEvent(getDocument().body,"htmx:beforeHistorySave",{path:t,historyElt:e}),saveToHistoryCache(t,e)),htmx.config.historyEnabled&&history.replaceState({htmx:!0},getDocument().title,location.href)}function pushUrlIntoHistory(e){htmx.config.getCacheBusterParam&&(e=e.replace(/org\.htmx\.cache-buster=[^&]*&?/,""),(endsWith(e,"&")||endsWith(e,"?"))&&(e=e.slice(0,-1))),htmx.config.historyEnabled&&history.pushState({htmx:!0},"",e),setCurrentPathForHistory(e)}function replaceUrlInHistory(e){htmx.config.historyEnabled&&history.replaceState({htmx:!0},"",e),setCurrentPathForHistory(e)}function settleImmediately(e){forEach(e,function(t){t.call(void 0)})}function loadHistoryFromServer(e){let t=new XMLHttpRequest,n={swapStyle:"innerHTML",swapDelay:0,settleDelay:0},r={path:e,xhr:t,historyElt:getHistoryElement(),swapSpec:n};t.open("GET",e,!0),htmx.config.historyRestoreAsHxRequest&&t.setRequestHeader("HX-Request","true"),t.setRequestHeader("HX-History-Restore-Request","true"),t.setRequestHeader("HX-Current-URL",location.href),t.onload=function(){this.status>=200&&this.status<400?(r.response=this.response,triggerEvent(getDocument().body,"htmx:historyCacheMissLoad",r),swap(r.historyElt,r.response,n,{contextElement:r.historyElt,historyRequest:!0}),setCurrentPathForHistory(r.path),triggerEvent(getDocument().body,"htmx:historyRestore",{path:e,cacheMiss:!0,serverResponse:r.response})):triggerErrorEvent(getDocument().body,"htmx:historyCacheMissLoadError",r)},triggerEvent(getDocument().body,"htmx:historyCacheMiss",r)&&t.send()}function restoreHistory(e){saveCurrentPageToHistory(),e=e||location.pathname+location.search;let t=getCachedHistory(e);if(t){let n={swapStyle:"innerHTML",swapDelay:0,settleDelay:0,scroll:t.scroll},r={path:e,item:t,historyElt:getHistoryElement(),swapSpec:n};triggerEvent(getDocument().body,"htmx:historyCacheHit",r)&&(swap(r.historyElt,t.content,n,{contextElement:r.historyElt,title:t.title}),setCurrentPathForHistory(r.path),triggerEvent(getDocument().body,"htmx:historyRestore",r))}else htmx.config.refreshOnHistoryMiss?htmx.location.reload(!0):loadHistoryFromServer(e)}function addRequestIndicatorClasses(e){let t=findAttributeTargets(e,"hx-indicator");return t==null&&(t=[e]),forEach(t,function(n){let r=getInternalData(n);r.requestCount=(r.requestCount||0)+1,n.classList.add.call(n.classList,htmx.config.requestClass)}),t}function disableElements(e){let t=findAttributeTargets(e,"hx-disabled-elt");return t==null&&(t=[]),forEach(t,function(n){let r=getInternalData(n);r.requestCount=(r.requestCount||0)+1,n.setAttribute("disabled",""),n.setAttribute("data-disabled-by-htmx","")}),t}function removeRequestIndicators(e,t){forEach(e.concat(t),function(n){let r=getInternalData(n);r.requestCount=(r.requestCount||1)-1}),forEach(e,function(n){getInternalData(n).requestCount===0&&n.classList.remove.call(n.classList,htmx.config.requestClass)}),forEach(t,function(n){getInternalData(n).requestCount===0&&(n.removeAttribute("disabled"),n.removeAttribute("data-disabled-by-htmx"))})}function haveSeenNode(e,t){for(let n=0;n<e.length;n++)if(e[n].isSameNode(t))return!0;return!1}function shouldInclude(e){let t=e;return t.name===""||t.name==null||t.disabled||closest(t,"fieldset[disabled]")||t.type==="button"||t.type==="submit"||t.tagName==="image"||t.tagName==="reset"||t.tagName==="file"?!1:t.type==="checkbox"||t.type==="radio"?t.checked:!0}function addValueToFormData(e,t,n){e!=null&&t!=null&&(Array.isArray(t)?t.forEach(function(r){n.append(e,r)}):n.append(e,t))}function removeValueFromFormData(e,t,n){if(e!=null&&t!=null){let r=n.getAll(e);Array.isArray(t)?r=r.filter(s=>t.indexOf(s)<0):r=r.filter(s=>s!==t),n.delete(e),forEach(r,s=>n.append(e,s))}}function getValueFromInput(e){return e instanceof HTMLSelectElement&&e.multiple?toArray(e.querySelectorAll("option:checked")).map(function(t){return t.value}):e instanceof HTMLInputElement&&e.files?toArray(e.files):e.value}function processInputValue(e,t,n,r,s){if(!(r==null||haveSeenNode(e,r))){if(e.push(r),shouldInclude(r)){let o=getRawAttribute(r,"name");addValueToFormData(o,getValueFromInput(r),t),s&&validateElement(r,n)}r instanceof HTMLFormElement&&(forEach(r.elements,function(o){e.indexOf(o)>=0?removeValueFromFormData(o.name,getValueFromInput(o),t):e.push(o),s&&validateElement(o,n)}),new FormData(r).forEach(function(o,i){o instanceof File&&o.name===""||addValueToFormData(i,o,t)}))}}function validateElement(e,t){let n=e;n.willValidate&&(triggerEvent(n,"htmx:validation:validate"),n.checkValidity()||(triggerEvent(n,"htmx:validation:failed",{message:n.validationMessage,validity:n.validity})&&!t.length&&htmx.config.reportValidityOfForms&&n.reportValidity(),t.push({elt:n,message:n.validationMessage,validity:n.validity})))}function overrideFormData(e,t){for(let n of t.keys())e.delete(n);return t.forEach(function(n,r){e.append(r,n)}),e}function getInputValues(e,t){let n=[],r=new FormData,s=new FormData,o=[],i=getInternalData(e);i.lastButtonClicked&&!bodyContains(i.lastButtonClicked)&&(i.lastButtonClicked=null);let a=e instanceof HTMLFormElement&&e.noValidate!==!0||getAttributeValue(e,"hx-validate")==="true";if(i.lastButtonClicked&&(a=a&&i.lastButtonClicked.formNoValidate!==!0),t!=="get"&&processInputValue(n,s,o,getRelatedForm(e),a),processInputValue(n,r,o,e,a),i.lastButtonClicked||e.tagName==="BUTTON"||e.tagName==="INPUT"&&getRawAttribute(e,"type")==="submit"){let c=i.lastButtonClicked||e,u=getRawAttribute(c,"name");addValueToFormData(u,c.value,s)}let l=findAttributeTargets(e,"hx-include");return forEach(l,function(c){processInputValue(n,r,o,asElement(c),a),matches(c,"form")||forEach(asParentNode(c).querySelectorAll(INPUT_SELECTOR),function(u){processInputValue(n,r,o,u,a)})}),overrideFormData(r,s),{errors:o,formData:r,values:formDataProxy(r)}}function appendParam(e,t,n){e!==""&&(e+="&"),String(n)==="[object Object]"&&(n=JSON.stringify(n));let r=encodeURIComponent(n);return e+=encodeURIComponent(t)+"="+r,e}function urlEncode(e){e=formDataFromObject(e);let t="";return e.forEach(function(n,r){t=appendParam(t,r,n)}),t}function getHeaders(e,t,n){let r={"HX-Request":"true","HX-Trigger":getRawAttribute(e,"id"),"HX-Trigger-Name":getRawAttribute(e,"name"),"HX-Target":getAttributeValue(t,"id"),"HX-Current-URL":location.href};return getValuesForElement(e,"hx-headers",!1,r),n!==void 0&&(r["HX-Prompt"]=n),getInternalData(e).boosted&&(r["HX-Boosted"]="true"),r}function filterValues(e,t){let n=getClosestAttributeValue(t,"hx-params");if(n){if(n==="none")return new FormData;if(n==="*")return e;if(n.indexOf("not ")===0)return forEach(n.slice(4).split(","),function(r){r=r.trim(),e.delete(r)}),e;{let r=new FormData;return forEach(n.split(","),function(s){s=s.trim(),e.has(s)&&e.getAll(s).forEach(function(o){r.append(s,o)})}),r}}else return e}function isAnchorLink(e){return!!getRawAttribute(e,"href")&&getRawAttribute(e,"href").indexOf("#")>=0}function getSwapSpecification(e,t){let n=t||getClosestAttributeValue(e,"hx-swap"),r={swapStyle:getInternalData(e).boosted?"innerHTML":htmx.config.defaultSwapStyle,swapDelay:htmx.config.defaultSwapDelay,settleDelay:htmx.config.defaultSettleDelay};if(htmx.config.scrollIntoViewOnBoost&&getInternalData(e).boosted&&!isAnchorLink(e)&&(r.show="top"),n){let i=splitOnWhitespace(n);if(i.length>0)for(let a=0;a<i.length;a++){let l=i[a];if(l.indexOf("swap:")===0)r.swapDelay=parseInterval(l.slice(5));else if(l.indexOf("settle:")===0)r.settleDelay=parseInterval(l.slice(7));else if(l.indexOf("transition:")===0)r.transition=l.slice(11)==="true";else if(l.indexOf("ignoreTitle:")===0)r.ignoreTitle=l.slice(12)==="true";else if(l.indexOf("scroll:")===0){var s=l.slice(7).split(":");let u=s.pop();var o=s.length>0?s.join(":"):null;r.scroll=u,r.scrollTarget=o}else if(l.indexOf("show:")===0){var s=l.slice(5).split(":");let d=s.pop();var o=s.length>0?s.join(":"):null;r.show=d,r.showTarget=o}else if(l.indexOf("focus-scroll:")===0){let c=l.slice(13);r.focusScroll=c=="true"}else a==0?r.swapStyle=l:logError("Unknown modifier in hx-swap: "+l)}}return r}function usesFormData(e){return getClosestAttributeValue(e,"hx-encoding")==="multipart/form-data"||matches(e,"form")&&getRawAttribute(e,"enctype")==="multipart/form-data"}function encodeParamsForBody(e,t,n){let r=null;return withExtensions(t,function(s){r==null&&(r=s.encodeParameters(e,n,t))}),r??(usesFormData(t)?overrideFormData(new FormData,formDataFromObject(n)):urlEncode(n))}function makeSettleInfo(e){return{tasks:[],elts:[e]}}function updateScrollState(e,t){let n=e[0],r=e[e.length-1];if(t.scroll){var s=null;t.scrollTarget&&(s=asElement(querySelectorExt(n,t.scrollTarget))),t.scroll==="top"&&(n||s)&&(s=s||n,s.scrollTop=0),t.scroll==="bottom"&&(r||s)&&(s=s||r,s.scrollTop=s.scrollHeight),typeof t.scroll=="number"&&getWindow().setTimeout(function(){window.scrollTo(0,t.scroll)},0)}if(t.show){var s=null;if(t.showTarget){let i=t.showTarget;t.showTarget==="window"&&(i="body"),s=asElement(querySelectorExt(n,i))}t.show==="top"&&(n||s)&&(s=s||n,s.scrollIntoView({block:"start",behavior:htmx.config.scrollBehavior})),t.show==="bottom"&&(r||s)&&(s=s||r,s.scrollIntoView({block:"end",behavior:htmx.config.scrollBehavior}))}}function getValuesForElement(e,t,n,r,s){if(r==null&&(r={}),e==null)return r;let o=getAttributeValue(e,t);if(o){let i=o.trim(),a=n;if(i==="unset")return null;i.indexOf("javascript:")===0?(i=i.slice(11),a=!0):i.indexOf("js:")===0&&(i=i.slice(3),a=!0),i.indexOf("{")!==0&&(i="{"+i+"}");let l;a?l=maybeEval(e,function(){return s?Function("event","return ("+i+")").call(e,s):Function("return ("+i+")").call(e)},{}):l=parseJSON(i);for(let c in l)l.hasOwnProperty(c)&&r[c]==null&&(r[c]=l[c])}return getValuesForElement(asElement(parentElt(e)),t,n,r,s)}function maybeEval(e,t,n){return htmx.config.allowEval?t():(triggerErrorEvent(e,"htmx:evalDisallowedError"),n)}function getHXVarsForElement(e,t,n){return getValuesForElement(e,"hx-vars",!0,n,t)}function getHXValsForElement(e,t,n){return getValuesForElement(e,"hx-vals",!1,n,t)}function getExpressionVars(e,t){return mergeObjects(getHXVarsForElement(e,t),getHXValsForElement(e,t))}function safelySetHeaderValue(e,t,n){if(n!==null)try{e.setRequestHeader(t,n)}catch{e.setRequestHeader(t,encodeURIComponent(n)),e.setRequestHeader(t+"-URI-AutoEncoded","true")}}function getPathFromResponse(e){if(e.responseURL)try{let t=new URL(e.responseURL);return t.pathname+t.search}catch{triggerErrorEvent(getDocument().body,"htmx:badResponseUrl",{url:e.responseURL})}}function hasHeader(e,t){return t.test(e.getAllResponseHeaders())}function ajaxHelper(e,t,n){if(e=e.toLowerCase(),n){if(n instanceof Element||typeof n=="string")return issueAjaxRequest(e,t,null,null,{targetOverride:resolveTarget(n)||DUMMY_ELT,returnPromise:!0});{let r=resolveTarget(n.target);return(n.target&&!r||n.source&&!r&&!resolveTarget(n.source))&&(r=DUMMY_ELT),issueAjaxRequest(e,t,resolveTarget(n.source),n.event,{handler:n.handler,headers:n.headers,values:n.values,targetOverride:r,swapOverride:n.swap,select:n.select,returnPromise:!0,push:n.push,replace:n.replace,selectOOB:n.selectOOB})}}else return issueAjaxRequest(e,t,null,null,{returnPromise:!0})}function hierarchyForElt(e){let t=[];for(;e;)t.push(e),e=e.parentElement;return t}function verifyPath(e,t,n){let r=new URL(t,location.protocol!=="about:"?location.href:window.origin),o=(location.protocol!=="about:"?location.origin:window.origin)===r.origin;return htmx.config.selfRequestsOnly&&!o?!1:triggerEvent(e,"htmx:validateUrl",mergeObjects({url:r,sameHost:o},n))}function formDataFromObject(e){if(e instanceof FormData)return e;let t=new FormData;for(let n in e)e.hasOwnProperty(n)&&(e[n]&&typeof e[n].forEach=="function"?e[n].forEach(function(r){t.append(n,r)}):typeof e[n]=="object"&&!(e[n]instanceof Blob)?t.append(n,JSON.stringify(e[n])):t.append(n,e[n]));return t}function formDataArrayProxy(e,t,n){return new Proxy(n,{get:function(r,s){return typeof s=="number"?r[s]:s==="length"?r.length:s==="push"?function(o){r.push(o),e.append(t,o)}:typeof r[s]=="function"?function(){r[s].apply(r,arguments),e.delete(t),r.forEach(function(o){e.append(t,o)})}:r[s]&&r[s].length===1?r[s][0]:r[s]},set:function(r,s,o){return r[s]=o,e.delete(t),r.forEach(function(i){e.append(t,i)}),!0}})}function formDataProxy(e){return new Proxy(e,{get:function(t,n){if(typeof n=="symbol"){let s=Reflect.get(t,n);return typeof s=="function"?function(){return s.apply(e,arguments)}:s}if(n==="toJSON")return()=>Object.fromEntries(e);if(n in t&&typeof t[n]=="function")return function(){return e[n].apply(e,arguments)};let r=e.getAll(n);if(r.length!==0)return r.length===1?r[0]:formDataArrayProxy(t,n,r)},set:function(t,n,r){return typeof n!="string"?!1:(t.delete(n),r&&typeof r.forEach=="function"?r.forEach(function(s){t.append(n,s)}):typeof r=="object"&&!(r instanceof Blob)?t.append(n,JSON.stringify(r)):t.append(n,r),!0)},deleteProperty:function(t,n){return typeof n=="string"&&t.delete(n),!0},ownKeys:function(t){return Reflect.ownKeys(Object.fromEntries(t))},getOwnPropertyDescriptor:function(t,n){return Reflect.getOwnPropertyDescriptor(Object.fromEntries(t),n)}})}function issueAjaxRequest(e,t,n,r,s,o){let i=null,a=null;if(s=s??{},s.returnPromise&&typeof Promise<"u")var l=new Promise(function(T,H){i=T,a=H});n==null&&(n=getDocument().body);let c=s.handler||handleAjaxResponse,u=s.select||null;if(!bodyContains(n))return maybeCall(i),l;let d=s.targetOverride||asElement(getTarget(n));if(d==null||d==DUMMY_ELT)return triggerErrorEvent(n,"htmx:targetError",{target:getClosestAttributeValue(n,"hx-target")}),maybeCall(a),l;let f=getInternalData(n),h=f.lastButtonClicked;if(h){let T=getRawAttribute(h,"formaction");T!=null&&(t=T);let H=getRawAttribute(h,"formmethod");if(H!=null)if(VERBS.includes(H.toLowerCase()))e=H;else return maybeCall(i),l}let p=getClosestAttributeValue(n,"hx-confirm");if(o===void 0&&triggerEvent(n,"htmx:confirm",{target:d,elt:n,path:t,verb:e,triggeringEvent:r,etc:s,issueRequest:function(G){return issueAjaxRequest(e,t,n,r,s,!!G)},question:p})===!1)return maybeCall(i),l;let g=n,m=getClosestAttributeValue(n,"hx-sync"),v=null,y=!1;if(m){let T=m.split(":"),H=T[0].trim();if(H==="this"?g=findThisElement(n,"hx-sync"):g=asElement(querySelectorExt(n,H)),m=(T[1]||"drop").trim(),f=getInternalData(g),m==="drop"&&f.xhr&&f.abortable!==!0)return maybeCall(i),l;if(m==="abort"){if(f.xhr)return maybeCall(i),l;y=!0}else m==="replace"?triggerEvent(g,"htmx:abort"):m.indexOf("queue")===0&&(v=(m.split(" ")[1]||"last").trim())}if(f.xhr)if(f.abortable)triggerEvent(g,"htmx:abort");else{if(v==null){if(r){let T=getInternalData(r);T&&T.triggerSpec&&T.triggerSpec.queue&&(v=T.triggerSpec.queue)}v==null&&(v="last")}return f.queuedRequests==null&&(f.queuedRequests=[]),v==="first"&&f.queuedRequests.length===0?f.queuedRequests.push(function(){issueAjaxRequest(e,t,n,r,s)}):v==="all"?f.queuedRequests.push(function(){issueAjaxRequest(e,t,n,r,s)}):v==="last"&&(f.queuedRequests=[],f.queuedRequests.push(function(){issueAjaxRequest(e,t,n,r,s)})),maybeCall(i),l}let x=new XMLHttpRequest;f.xhr=x,f.abortable=y;let b=function(){f.xhr=null,f.abortable=!1,f.queuedRequests!=null&&f.queuedRequests.length>0&&f.queuedRequests.shift()()},j=getClosestAttributeValue(n,"hx-prompt");if(j){var V=prompt(j);if(V===null||!triggerEvent(n,"htmx:prompt",{prompt:V,target:d}))return maybeCall(i),b(),l}if(p&&!o&&!confirm(p))return maybeCall(i),b(),l;let B=getHeaders(n,d,V);e!=="get"&&!usesFormData(n)&&(B["Content-Type"]="application/x-www-form-urlencoded"),s.headers&&(B=mergeObjects(B,s.headers));let U=getInputValues(n,e),E=U.errors,S=U.formData;s.values&&overrideFormData(S,formDataFromObject(s.values));let _=formDataFromObject(getExpressionVars(n,r)),C=overrideFormData(S,_),w=filterValues(C,n);htmx.config.getCacheBusterParam&&e==="get"&&w.set("org.htmx.cache-buster",getRawAttribute(d,"id")||"true"),(t==null||t==="")&&(t=location.href);let k=getValuesForElement(n,"hx-request"),L=getInternalData(n).boosted,z=htmx.config.methodsThatUseUrlParams.indexOf(e)>=0,D={boosted:L,useUrlParams:z,formData:w,parameters:formDataProxy(w),unfilteredFormData:C,unfilteredParameters:formDataProxy(C),headers:B,elt:n,target:d,verb:e,errors:E,withCredentials:s.credentials||k.credentials||htmx.config.withCredentials,timeout:s.timeout||k.timeout||htmx.config.timeout,path:t,triggeringEvent:r};if(!triggerEvent(n,"htmx:configRequest",D))return maybeCall(i),b(),l;if(t=D.path,e=D.verb,B=D.headers,w=formDataFromObject(D.parameters),E=D.errors,z=D.useUrlParams,E&&E.length>0)return triggerEvent(n,"htmx:validation:halted",D),maybeCall(i),b(),l;let ne=t.split("#"),ae=ne[0],Se=ne[1],I=t;if(z&&(I=ae,!w.keys().next().done&&(I.indexOf("?")<0?I+="?":I+="&",I+=urlEncode(w),Se&&(I+="#"+Se))),!verifyPath(n,I,D))return triggerErrorEvent(n,"htmx:invalidPath",D),maybeCall(a),b(),l;if(x.open(e.toUpperCase(),I,!0),x.overrideMimeType("text/html"),x.withCredentials=D.withCredentials,x.timeout=D.timeout,!k.noHeaders){for(let T in B)if(B.hasOwnProperty(T)){let H=B[T];safelySetHeaderValue(x,T,H)}}let A={xhr:x,target:d,requestConfig:D,etc:s,boosted:L,select:u,pathInfo:{requestPath:t,finalRequestPath:I,responsePath:null,anchor:Se}};if(x.onload=function(){try{let T=hierarchyForElt(n);if(A.pathInfo.responsePath=getPathFromResponse(x),c(n,A),A.keepIndicators!==!0&&removeRequestIndicators(J,de),triggerEvent(n,"htmx:afterRequest",A),triggerEvent(n,"htmx:afterOnLoad",A),!bodyContains(n)){let H=null;for(;T.length>0&&H==null;){let G=T.shift();bodyContains(G)&&(H=G)}H&&(triggerEvent(H,"htmx:afterRequest",A),triggerEvent(H,"htmx:afterOnLoad",A))}maybeCall(i)}catch(T){throw triggerErrorEvent(n,"htmx:onLoadError",mergeObjects({error:T},A)),T}finally{b()}},x.onerror=function(){removeRequestIndicators(J,de),triggerErrorEvent(n,"htmx:afterRequest",A),triggerErrorEvent(n,"htmx:sendError",A),maybeCall(a),b()},x.onabort=function(){removeRequestIndicators(J,de),triggerErrorEvent(n,"htmx:afterRequest",A),triggerErrorEvent(n,"htmx:sendAbort",A),maybeCall(a),b()},x.ontimeout=function(){removeRequestIndicators(J,de),triggerErrorEvent(n,"htmx:afterRequest",A),triggerErrorEvent(n,"htmx:timeout",A),maybeCall(a),b()},!triggerEvent(n,"htmx:beforeRequest",A))return maybeCall(i),b(),l;var J=addRequestIndicatorClasses(n),de=disableElements(n);forEach(["loadstart","loadend","progress","abort"],function(T){forEach([x,x.upload],function(H){H.addEventListener(T,function(G){triggerEvent(n,"htmx:xhr:"+T,{lengthComputable:G.lengthComputable,loaded:G.loaded,total:G.total})})})}),triggerEvent(n,"htmx:beforeSend",A);let nt=z?null:encodeParamsForBody(x,n,w);return x.send(nt),l}function determineHistoryUpdates(e,t){let n=t.xhr,r=null,s=null;if(hasHeader(n,/HX-Push:/i)?(r=n.getResponseHeader("HX-Push"),s="push"):hasHeader(n,/HX-Push-Url:/i)?(r=n.getResponseHeader("HX-Push-Url"),s="push"):hasHeader(n,/HX-Replace-Url:/i)&&(r=n.getResponseHeader("HX-Replace-Url"),s="replace"),r)return r==="false"?{}:{type:s,path:r};let o=t.pathInfo.finalRequestPath,i=t.pathInfo.responsePath,a=t.etc.push||getClosestAttributeValue(e,"hx-push-url"),l=t.etc.replace||getClosestAttributeValue(e,"hx-replace-url"),c=getInternalData(e).boosted,u=null,d=null;return a?(u="push",d=a):l?(u="replace",d=l):c&&(u="push",d=i||o),d?d==="false"?{}:(d==="true"&&(d=i||o),t.pathInfo.anchor&&d.indexOf("#")===-1&&(d=d+"#"+t.pathInfo.anchor),{type:u,path:d}):{}}function codeMatches(e,t){var n=new RegExp(e.code);return n.test(t.toString(10))}function resolveResponseHandling(e){for(var t=0;t<htmx.config.responseHandling.length;t++){var n=htmx.config.responseHandling[t];if(codeMatches(n,e.status))return n}return{swap:!1}}function handleTitle(e){if(e){let t=find("title");t?t.textContent=e:window.document.title=e}}function resolveRetarget(e,t){if(t==="this")return e;let n=asElement(querySelectorExt(e,t));if(n==null)throw triggerErrorEvent(e,"htmx:targetError",{target:t}),new Error(`Invalid re-target ${t}`);return n}function handleAjaxResponse(e,t){let n=t.xhr,r=t.target,s=t.etc,o=t.select;if(!triggerEvent(e,"htmx:beforeOnLoad",t))return;if(hasHeader(n,/HX-Trigger:/i)&&handleTriggerHeader(n,"HX-Trigger",e),hasHeader(n,/HX-Location:/i)){let y=n.getResponseHeader("HX-Location");var i={};y.indexOf("{")===0&&(i=parseJSON(y),y=i.path,delete i.path),i.push=i.push||"true",ajaxHelper("get",y,i);return}let a=hasHeader(n,/HX-Refresh:/i)&&n.getResponseHeader("HX-Refresh")==="true";if(hasHeader(n,/HX-Redirect:/i)){t.keepIndicators=!0,htmx.location.href=n.getResponseHeader("HX-Redirect"),a&&htmx.location.reload();return}if(a){t.keepIndicators=!0,htmx.location.reload();return}let l=determineHistoryUpdates(e,t),c=resolveResponseHandling(n),u=c.swap,d=!!c.error,f=htmx.config.ignoreTitle||c.ignoreTitle,h=c.select;c.target&&(t.target=resolveRetarget(e,c.target));var p=s.swapOverride;p==null&&c.swapOverride&&(p=c.swapOverride),hasHeader(n,/HX-Retarget:/i)&&(t.target=resolveRetarget(e,n.getResponseHeader("HX-Retarget"))),hasHeader(n,/HX-Reswap:/i)&&(p=n.getResponseHeader("HX-Reswap"));var g=n.response,m=mergeObjects({shouldSwap:u,serverResponse:g,isError:d,ignoreTitle:f,selectOverride:h,swapOverride:p},t);if(!(c.event&&!triggerEvent(r,c.event,m))&&triggerEvent(r,"htmx:beforeSwap",m)){if(r=m.target,g=m.serverResponse,d=m.isError,f=m.ignoreTitle,h=m.selectOverride,p=m.swapOverride,t.target=r,t.failed=d,t.successful=!d,m.shouldSwap){n.status===286&&cancelPolling(e),withExtensions(e,function(b){g=b.transformResponse(g,n,e)}),l.type&&saveCurrentPageToHistory();var v=getSwapSpecification(e,p);v.hasOwnProperty("ignoreTitle")||(v.ignoreTitle=f),r.classList.add(htmx.config.swappingClass),o&&(h=o),hasHeader(n,/HX-Reselect:/i)&&(h=n.getResponseHeader("HX-Reselect"));let y=s.selectOOB||getClosestAttributeValue(e,"hx-select-oob"),x=getClosestAttributeValue(e,"hx-select");swap(r,g,v,{select:h==="unset"?null:h||x,selectOOB:y,eventInfo:t,anchor:t.pathInfo.anchor,contextElement:e,afterSwapCallback:function(){if(hasHeader(n,/HX-Trigger-After-Swap:/i)){let b=e;bodyContains(e)||(b=getDocument().body),handleTriggerHeader(n,"HX-Trigger-After-Swap",b)}},afterSettleCallback:function(){if(hasHeader(n,/HX-Trigger-After-Settle:/i)){let b=e;bodyContains(e)||(b=getDocument().body),handleTriggerHeader(n,"HX-Trigger-After-Settle",b)}},beforeSwapCallback:function(){l.type&&(triggerEvent(getDocument().body,"htmx:beforeHistoryUpdate",mergeObjects({history:l},t)),l.type==="push"?(pushUrlIntoHistory(l.path),triggerEvent(getDocument().body,"htmx:pushedIntoHistory",{path:l.path})):(replaceUrlInHistory(l.path),triggerEvent(getDocument().body,"htmx:replacedInHistory",{path:l.path})))}})}d&&triggerErrorEvent(e,"htmx:responseError",mergeObjects({error:"Response Status Error Code "+n.status+" from "+t.pathInfo.requestPath},t))}}let extensions={};function extensionBase(){return{init:function(e){return null},getSelectors:function(){return null},onEvent:function(e,t){return!0},transformResponse:function(e,t,n){return e},isInlineSwap:function(e){return!1},handleSwap:function(e,t,n,r){return!1},encodeParameters:function(e,t,n){return null}}}function defineExtension(e,t){t.init&&t.init(internalAPI),extensions[e]=mergeObjects(extensionBase(),t)}function removeExtension(e){delete extensions[e]}function getExtensions(e,t,n){if(t==null&&(t=[]),e==null)return t;n==null&&(n=[]);let r=getAttributeValue(e,"hx-ext");return r&&forEach(r.split(","),function(s){if(s=s.replace(/ /g,""),s.slice(0,7)=="ignore:"){n.push(s.slice(7));return}if(n.indexOf(s)<0){let o=extensions[s];o&&t.indexOf(o)<0&&t.push(o)}}),getExtensions(asElement(parentElt(e)),t,n)}var isReady=!1;getDocument().addEventListener("DOMContentLoaded",function(){isReady=!0});function ready(e){isReady||getDocument().readyState==="complete"?e():getDocument().addEventListener("DOMContentLoaded",e)}function insertIndicatorStyles(){if(htmx.config.includeIndicatorStyles!==!1){let e=htmx.config.inlineStyleNonce?` nonce="${htmx.config.inlineStyleNonce}"`:"",t=htmx.config.indicatorClass,n=htmx.config.requestClass;getDocument().head.insertAdjacentHTML("beforeend",`<style${e}>.${t}{opacity:0;visibility: hidden} .${n} .${t}, .${n}.${t}{opacity:1;visibility: visible;transition: opacity 200ms ease-in}</style>`)}}function getMetaConfig(){let e=getDocument().querySelector('meta[name="htmx-config"]');return e?parseJSON(e.content):null}function mergeMetaConfig(){let e=getMetaConfig();e&&(htmx.config=mergeObjects(htmx.config,e))}return ready(function(){mergeMetaConfig(),insertIndicatorStyles();let e=getDocument().body;processNode(e);let t=getDocument().querySelectorAll("[hx-trigger='restored'],[data-hx-trigger='restored']");e.addEventListener("htmx:abort",function(r){let s=r.detail.elt||r.target,o=getInternalData(s);o&&o.xhr&&o.xhr.abort()});let n=window.onpopstate?window.onpopstate.bind(window):null;window.onpopstate=function(r){r.state&&r.state.htmx?(restoreHistory(),forEach(t,function(s){triggerEvent(s,"htmx:restored",{document:getDocument(),triggerEvent})})):n&&n(r)},getWindow().setTimeout(function(){triggerEvent(e,"htmx:load",{}),e=null},0)}),htmx}(),Xu=Ec;var wc={"--bg-base":"240 20% 97%","--bg-elevated":"0 0% 100%","--bg-glass":"0 0% 100% / 0.55","--bg-glass-hover":"0 0% 100% / 0.72","--bg-glass-active":"0 0% 100% / 0.85","--bg-surface":"220 14% 96%","--bg-surface-hover":"220 14% 93%","--bg-overlay":"220 20% 96% / 0.8","--border-glass":"0 0% 100% / 0.6","--border-subtle":"220 13% 91%","--border-focus":"221 83% 53%","--text-primary":"220 14% 10%","--text-secondary":"220 9% 43%","--text-tertiary":"220 9% 60%","--text-inverse":"0 0% 100%","--accent":"221 83% 53%","--accent-hover":"221 83% 47%","--accent-subtle":"221 83% 53% / 0.08","--accent-glow":"221 83% 53% / 0.15","--success":"142 71% 45%","--warning":"38 92% 50%","--danger":"0 72% 51%","--danger-subtle":"0 72% 51% / 0.08","--shadow-sm":"0 1px 2px hsl(220 14% 10% / 0.04), 0 1px 3px hsl(220 14% 10% / 0.03)","--shadow-md":"0 4px 6px hsl(220 14% 10% / 0.04), 0 2px 4px hsl(220 14% 10% / 0.03)","--shadow-lg":"0 10px 25px hsl(220 14% 10% / 0.06), 0 4px 10px hsl(220 14% 10% / 0.04)","--shadow-glass":"0 8px 32px hsl(220 14% 10% / 0.06), inset 0 1px 0 hsl(0 0% 100% / 0.6)","--blur-glass":"20px","--blur-bg":"40px","--noise-opacity":"0.015","--scrollbar-track":"220 14% 96%","--scrollbar-thumb":"220 9% 82%","--code-bg":"220 14% 96%"},Sc={"--bg-base":"224 25% 8%","--bg-elevated":"224 22% 12%","--bg-glass":"224 22% 14% / 0.6","--bg-glass-hover":"224 22% 16% / 0.72","--bg-glass-active":"224 22% 18% / 0.85","--bg-surface":"224 20% 14%","--bg-surface-hover":"224 20% 18%","--bg-overlay":"224 25% 8% / 0.85","--border-glass":"224 15% 22% / 0.6","--border-subtle":"224 15% 20%","--border-focus":"217 91% 60%","--text-primary":"220 14% 95%","--text-secondary":"220 9% 65%","--text-tertiary":"220 9% 46%","--text-inverse":"220 14% 10%","--accent":"217 91% 60%","--accent-hover":"217 91% 67%","--accent-subtle":"217 91% 60% / 0.1","--accent-glow":"217 91% 60% / 0.12","--success":"142 71% 45%","--warning":"38 92% 50%","--danger":"0 72% 55%","--danger-subtle":"0 72% 55% / 0.1","--shadow-sm":"0 1px 2px hsl(0 0% 0% / 0.2), 0 1px 3px hsl(0 0% 0% / 0.15)","--shadow-md":"0 4px 6px hsl(0 0% 0% / 0.2), 0 2px 4px hsl(0 0% 0% / 0.15)","--shadow-lg":"0 10px 25px hsl(0 0% 0% / 0.3), 0 4px 10px hsl(0 0% 0% / 0.2)","--shadow-glass":"0 8px 32px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(0 0% 100% / 0.04)","--blur-glass":"20px","--blur-bg":"40px","--noise-opacity":"0.03","--scrollbar-track":"224 20% 12%","--scrollbar-thumb":"224 15% 26%","--code-bg":"224 20% 10%"},_c={light:wc,dark:Sc};function rr(e){return e==="auto"?window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light":e}function sr(e){let t=document.documentElement;t.setAttribute("data-theme",e);let n=_c[e];for(let[r,s]of Object.entries(n))t.style.setProperty(r,s)}var bo={mode:"auto",resolved:"dark",init(){let e=localStorage.getItem("theme-preference")||"auto";["future","system"].includes(e)&&(e="dark"),e==="bare"&&(e="light"),["light","dark","auto"].includes(e)||(e="auto"),this.mode=e,this.resolved=rr(this.mode),sr(this.resolved),localStorage.setItem("theme-preference",this.mode),window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>{this.mode==="auto"&&(this.resolved=rr("auto"),sr(this.resolved))})},set(e){this.mode=e,this.resolved=rr(e),sr(this.resolved),localStorage.setItem("theme-preference",e)}};var xo={query:"",mode:"hybrid",project:"",tool:"",date:"",dateFrom:"",dateTo:"",sortBy:"relevance",semanticHighlights:!1,page:1,pageSize:20,totalPages:0,totalResults:0,loading:!1,searchTimeMs:0,history:[],maxHistory:50,init(){this._restoreState(),this._loadHistory()},setQuery(e){this.query=e},setMode(e){this.mode=e,this.page=1},setProject(e){this.project=e,this.page=1},setTool(e){this.tool=e,this.page=1},setDate(e){this.date=e,this.page=1},setSortBy(e){this.sortBy=e,this.page=1},setPage(e){this.page=e},buildSearchParams(){let e=new URLSearchParams;return e.set("q",this.query),e.set("mode",this.mode),e.set("page",String(this.page)),e.set("page_size",String(this.pageSize)),this.project&&e.set("project",this.project),this.tool&&e.set("tool",this.tool),this.sortBy!=="relevance"&&e.set("sort_by",this.sortBy),this.date==="custom"?(this.dateFrom&&e.set("date_from",this.dateFrom),this.dateTo&&e.set("date_to",this.dateTo)):this.date&&e.set("date",this.date),this.semanticHighlights&&e.set("semantic_highlights","true"),e},addToHistory(e){e.trim()&&(this.history=this.history.filter(t=>t.query!==e),this.history.unshift({query:e,mode:this.mode,timestamp:Date.now()}),this.history.length>this.maxHistory&&(this.history=this.history.slice(0,this.maxHistory)),this._saveHistory())},clearHistory(){this.history=[],this._saveHistory()},saveState(){let e={query:this.query,mode:this.mode,project:this.project,tool:this.tool,date:this.date,dateFrom:this.dateFrom,dateTo:this.dateTo,sortBy:this.sortBy,page:this.page,semanticHighlights:this.semanticHighlights};sessionStorage.setItem("searchState",JSON.stringify(e))},_restoreState(){let e=sessionStorage.getItem("searchState");if(!e)return;let t=JSON.parse(e);Object.assign(this,t)},_loadHistory(){let e=localStorage.getItem("searchHistory");e&&(this.history=JSON.parse(e))},_saveHistory(){localStorage.setItem("searchHistory",JSON.stringify(this.history))}};var Eo={sidebarCollapsed:!1,rightPanelOpen:!1,activeNav:"search",helpModalOpen:!1,bulkMode:!1,init(){let e=localStorage.getItem("sidebarCollapsed");e!==null&&(this.sidebarCollapsed=e==="true")},toggleSidebar(){this.sidebarCollapsed=!this.sidebarCollapsed,localStorage.setItem("sidebarCollapsed",String(this.sidebarCollapsed))},toggleRightPanel(){this.rightPanelOpen=!this.rightPanelOpen},setActiveNav(e){this.activeNav=e},toggleHelpModal(){this.helpModalOpen=!this.helpModalOpen},toggleBulkMode(){this.bulkMode=!this.bulkMode}};var wo={provider:"ollama",model:"",sessionId:"",temperature:null,maxTokens:null,systemPrompt:"",query:"",answer:"",status:"",sending:!1,sources:[],controller:null,init(){let e=localStorage.getItem("chatProvider");e&&(this.provider=e);let t=localStorage.getItem("chatModel");t&&(this.model=t);let n=localStorage.getItem("chatSessionId");n&&(this.sessionId=n)},setProvider(e){this.provider=e,localStorage.setItem("chatProvider",e)},setModel(e){this.model=e,localStorage.setItem("chatModel",e)},async send(){if(!this.query.trim()||this.sending)return;this.sending=!0,this.answer="",this.sources=[],this.status="Searching for relevant context...",this.controller=new AbortController;let e={query:this.query,model_provider:this.provider};this.model&&(e.model_name=this.model),this.sessionId&&(e.session_id=this.sessionId),this.temperature!==null&&(e.temperature=this.temperature),this.maxTokens!==null&&(e.max_tokens=this.maxTokens),this.systemPrompt&&(e.system_prompt=this.systemPrompt);try{let t=await fetch("/api/chat-rag",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e),signal:this.controller.signal});if(!t.ok){let r=await t.json().catch(()=>({detail:"Unknown error"}));throw new Error(r.detail||`HTTP ${t.status}`)}let n=await t.json();this.answer=n?.answer??"",this.sources=Array.isArray(n?.sources)?n.sources:[],n?.session_id&&(this.sessionId=n.session_id,localStorage.setItem("chatSessionId",this.sessionId)),this.status=""}catch(t){t instanceof Error&&t.name==="AbortError"?this.status="Stopped":this.status=`Error: ${t instanceof Error?t.message:String(t)}`}finally{this.sending=!1,this.controller=null}},stop(){this.controller&&this.controller.abort()},clear(){this.query="",this.answer="",this.sources=[],this.status="",this.sending=!1,this.sessionId="",localStorage.removeItem("chatSessionId")}};var So={snapshotName:"",isSnapshot:!1,bannerVisible:!1,init(){let e=sessionStorage.getItem("activeDataset");if(e){let t=JSON.parse(e);this.snapshotName=t.snapshotName||"",this.isSnapshot=t.isSnapshot||!1,this.bannerVisible=this.isSnapshot}},setSnapshot(e){this.snapshotName=e,this.isSnapshot=!!e,this.bannerVisible=this.isSnapshot,this._save()},clearSnapshot(){this.snapshotName="",this.isSnapshot=!1,this.bannerVisible=!1,this._save()},_save(){sessionStorage.setItem("activeDataset",JSON.stringify({snapshotName:this.snapshotName,isSnapshot:this.isSnapshot}))}};function or(){document.querySelectorAll("pre code").forEach(e=>{if(e.parentElement?.querySelector(".code-copy-btn")||e.parentElement?.hasAttribute("data-no-copy"))return;let t=document.createElement("button");t.className="code-copy-btn",t.textContent="Copy",t.setAttribute("type","button"),t.addEventListener("click",()=>{let n=e.textContent||"";navigator.clipboard.writeText(n).then(()=>{t.textContent="Copied!",setTimeout(()=>{t.textContent="Copy"},2e3)},()=>{t.textContent="Failed",setTimeout(()=>{t.textContent="Copy"},2e3)})}),e.parentElement?.style.setProperty("position","relative"),e.parentElement?.appendChild(t)})}function _o(e,t){return{phase:"Initializing...",current:0,total:0,pct:-1,done:!1,message:"",_es:null,start(){this._es=new EventSource(e),this._es.addEventListener("progress",n=>{let r=JSON.parse(n.data);this.phase=r.phase,this.current=r.current,this.total=r.total,this.pct=r.pct}),this._es.addEventListener("done",n=>{let r=JSON.parse(n.data);this.phase="Done",this.pct=100,this.done=!0,this.message=r.message,this._es?.close(),t&&setTimeout(()=>{htmx.ajax("GET",t,{target:"#results",swap:"innerHTML"})},1500)}),this._es.addEventListener("error",()=>{this._es?.close(),this.done||(this.phase="Error \u2014 connection lost",this.pct=0)})},destroy(){this._es&&(this._es.close(),this._es=null)}}}window.Alpine=fe;fe.store("theme",bo);fe.store("search",xo);fe.store("layout",Eo);fe.store("chat",wo);fe.store("dataset",So);fe.data("rebuildProgress",_o);fe.start();Promise.resolve().then(()=>(ea(),Nu)).catch(e=>{console.error("Legacy web bootstrap failed:",e)});or();document.addEventListener("htmx:afterSwap",()=>{or()});
//# sourceMappingURL=main.js.map
