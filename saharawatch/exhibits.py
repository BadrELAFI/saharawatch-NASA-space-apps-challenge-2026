"""Physical exhibit mounts around unmodified scientific charts and images."""
from contextlib import contextmanager
import html

import streamlit as st


@contextmanager
def exhibit(label, title, key, kind='report'):
    with st.container(key='exhibit_'+key):
        st.html(f'<div class="exhibit-heading exhibit-{html.escape(kind)}"><span>{html.escape(label)}</span>'
                f'<strong>{html.escape(title)}</strong><i aria-hidden="true">Filed observations</i></div>')
        yield


def filed_stamp(text='ASSESSMENT FILED'):
    st.html(f'<div class="filed-stamp" role="status">{html.escape(text)}</div>')
