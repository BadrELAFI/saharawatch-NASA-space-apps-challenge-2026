"""Keep shortcut navigation and native tab selection synchronized."""
import streamlit as st


WORKSPACES = ['01 / Evidence atlas','Satellite images','02 / Cross-examine','03 / Case files',
              '04 / Field notebook','05 / The science','06 / Rainfall deficits & SPI']


def activate_workspace(label):
    if label not in WORKSPACES:
        raise ValueError('Unknown workspace.')
    st.session_state.update(workspace_tab=label,workspace_initial_label=label,
                           workspace_revision=st.session_state.get('workspace_revision',0)+1)
