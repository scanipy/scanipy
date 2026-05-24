"""Notebook-converted coverage: .py derived from a .ipynb (irregular structure).

Construct under test: parse-success on jupyter-export structure (DOC §4.3
`notebooks-converted`) -- `# In[N]:` cell markers, top-level expression statements,
and re-binding of the same name across cells. This is the parse-success stressor;
its call edges (`step_two -> step_one`) are static.
"""

# coding: utf-8

# In[1]:


def step_one(x):
    y = x + 1
    return y


# In[2]:


def step_two(x):
    z = step_one(x)
    return z


# In[3]:


result = step_two(10)
result
