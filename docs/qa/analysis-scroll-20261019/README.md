# Analysis scroll repair preview

The live page was reproduced at 1280 × 720 with the complete Time table open: a downward wheel over a table cell left pageY at 4554 despite a page maximum of 5046. Its wrapper had no vertical overflow of its own but contained vertical scroll chaining. Seven in-page chart/table/list rules now retain horizontal containment while allowing vertical chaining. Real dialogs and map controls keep their existing behavior.

Background navigation synchronization now moves only its internal topic rail. It cannot reclaim the outer page position after chart updates. Explicit topic clicks and keyboard navigation still reveal the requested heading.

At 844 × 390, the sticky Analysis toolbar occupied 252.9px plus its8px top gap. When fewer than240px would remain for results, the toolbar now flows with the page; normal sizing restores sticky controls. Its topic rail and heading reveal account for either mode.

Focused actual-installer navigation/resize regression, A/B navigation, readiness view, and six release preparation tests pass. Hosted wheel, short-screen, phone-size and modal checks follow in browser.json. Production is not changed by this preview.

Storage: reuse the single existing Pages stage; no new dataset, database, release-tree copy or R2 object is created. Stage net growth957bytes; expected source/Git/QA growth below1MiB and no new file above100MiB. Canonical validated production remains a49d5164 (83e1ed4), retained rollback16b1c76f (94384c0). The stage is the sole current repair candidate, reproducible with prepare_workspace_analysis_release.py --refresh-stage. Hosted preview is temporary review material, to be superseded by a later approved release; no deletion is performed.
