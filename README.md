flowchart TD
  %% ====== 入口与登录 ======
  A[/ /  → 302 /home /] --> H[["/home<br/>主界面"]]

  subgraph Auth[认证]
    L[["/login<br/>GET,POST"]]
    O[["/logout<br/>GET"]]
  end
  L --> H
  O --> L

  %% ====== 主菜单 ======
  H --> I[["/data-input<br/>GET"]]
  H --> D[["/data_analysis<br/>GET,POST"]]
  H --> M[["/data_manage → /admin<br/>GET"]]
  H --> V[["/visualization<br/>GET"]]
  H --> S1[["/survey/dr24<br/>GET"]]
  H --> S2[["/survey/ffq<br/>GET"]]

  %% ====== 数据输入与上传 ======
  I --> U[["/upload<br/>GET,POST"]]
  U --> V
  U -. 静态图/文件 .-> ST[["/static/<path>"]]

  %% ====== 数据分析：单文件类 ======
  subgraph Analyses[数据分析（/data_analysis POST）]
    D --> D_ffq[[ffq → /download/ffq]]
    D --> D_24h[[24h → /download/24h]]
    D --> D_assess[[assessment → /download/assessment]]
    D --> D_cat[[ffq_category → /download/ffq_category]]
    D --> D_pca[[pca_pattern → /download/pca_pattern]]
    D --> D_valid[[validation_ffq → /download/validation_ffq]]
    D --> D_sumweb[[sum_dr_nutrients_for_web → /download/sum_dr_nutrients_for_web]]

    %% 多文件/文件夹上传
    D --> D_dr[[concat_dr (multiple files) → /download/dr24_zip]]
    D --> D_ffqMerge[[ffq_merge (multiple files) → /download/ffq_merge]]
  end

  %% ====== 问卷嵌入流 ======
  S1 --> S1_embed[["survey_embed.html（iframe）"]]
  S1_embed --> S1_raw[["/survey/dr24/raw<br/>DR-24离线页"]]

  S2 --> S2_embed[["survey_embed copy.html（iframe）"]]
  S2_embed --> S2_raw[["/survey/ffq/raw<br/>Full-FFQ离线页"]]

  %% ====== 下载中心 ======
  subgraph DL[统一下载 /download/<filetype>]
    D_ffq -.-> DL1[ffq]
    D_24h -.-> DL2[24h]
    D_assess -.-> DL3[assessment]
    D_cat -.-> DL4[ffq_category]
    D_pca -.-> DL5[pca_pattern]
    D_valid -.-> DL6[validation_ffq]
    D_sumweb -.-> DL7[sum_dr_nutrients_for_web]
    D_dr -.-> DL8[dr24_zip]
    D_ffqMerge -.-> DL9[ffq_merge]
  end
