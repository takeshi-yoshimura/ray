import pytest

import ray


@ray.remote
class Counter:
    def __init__(self, init_value=0):
        self.i = init_value

    def inc(self):
        self.i += 1

    def get(self):
        return self.i


def test_basic_task_dag():
    ct = Counter.remote()

    @ray.remote
    def a():
        ray.get(ct.inc.remote())
        return 2

    @ray.remote
    def b(x):
        ray.get(ct.inc.remote())
        return x * 2

    @ray.remote
    def c(x):
        ray.get(ct.inc.remote())
        return x + 1

    @ray.remote
    def d(x, y):
        ray.get(ct.inc.remote())
        return x + y

    a_ref = a._bind()
    b_ref = b._bind(a_ref)
    c_ref = c._bind(a_ref)
    d_ref = d._bind(b_ref, c_ref)
    d1_ref = d._bind(d_ref, d_ref)
    d2_ref = d._bind(d1_ref, d_ref)
    dag = d._bind(d2_ref, d_ref)
    print(dag)

    assert ray.get(dag.execute()) == 28
    assert ray.get(ct.get.remote()) == 7


def test_basic_task_dag_with_options():
    ct = Counter.remote()

    @ray.remote
    def a():
        ray.get(ct.inc.remote())
        return 2

    @ray.remote
    def b(x):
        ray.get(ct.inc.remote())
        return x * 2

    @ray.remote
    def c(x):
        ray.get(ct.inc.remote())
        return x + 1

    @ray.remote
    def d(x, y):
        ray.get(ct.inc.remote())
        return x + y

    a_ref = a._bind()
    b_ref = b.options(name="b", num_returns=1)._bind(a_ref)
    c_ref = c.options(name="c", max_retries=3)._bind(a_ref)
    dag = d.options(name="d", num_cpus=2)._bind(b_ref, c_ref)

    print(dag)

    assert ray.get(dag.execute()) == 7
    assert ray.get(ct.get.remote()) == 4

    assert b_ref.get_options().get("name") == "b"
    assert b_ref.get_options().get("num_returns") == 1
    assert c_ref.get_options().get("name") == "c"
    assert c_ref.get_options().get("max_retries") == 3
    assert dag.get_options().get("name") == "d"
    assert dag.get_options().get("num_cpus") == 2


def test_invalid_task_options():
    """
    Test to ensure options used in DAG binding are applied, and will throw
    as expected even given invalid values.
    """

    @ray.remote
    def a():
        return 2

    @ray.remote
    def b(x):
        return x * 2

    a_ref = a._bind()
    dag = b._bind(a_ref)

    # Ensure current DAG is executable
    assert ray.get(dag.execute()) == 4
    invalid_dag = b.options(num_cpus=-1)._bind(a_ref)
    with pytest.raises(ValueError, match=".*Resource quantities may not be negative.*"):
        ray.get(invalid_dag.execute())


def test_node_accessors():
    @ray.remote
    def a(*a, **kw):
        pass

    tmp1 = a._bind()
    tmp2 = a._bind()
    tmp3 = a._bind()
    node = a._bind(1, tmp1, x=tmp2, y={"foo": tmp3})
    assert node.get_args() == (1, tmp1)
    assert node.get_kwargs() == {"x": tmp2, "y": {"foo": tmp3}}
    assert node._get_toplevel_child_nodes() == {tmp1, tmp2}
    assert node._get_all_child_nodes() == {tmp1, tmp2, tmp3}

    tmp4 = a._bind()
    tmp5 = a._bind()
    replace = {tmp1: tmp4, tmp2: tmp4, tmp3: tmp5}
    n2 = node._apply_and_replace_all_child_nodes(lambda x: replace[x])
    assert n2._get_all_child_nodes() == {tmp4, tmp5}


def test_nested_args():
    ct = Counter.remote()

    @ray.remote
    def a():
        ray.get(ct.inc.remote())
        return 2

    @ray.remote
    def b(**kwargs):
        ray.get(ct.inc.remote())
        return kwargs["x"] * 2

    @ray.remote
    def c(**kwargs):
        ray.get(ct.inc.remote())
        return kwargs["x"] + 1

    @ray.remote
    def d(nested):
        ray.get(ct.inc.remote())
        return ray.get(nested["x"]) + ray.get(nested["y"])

    a_ref = a._bind()
    b_ref = b._bind(x=a_ref)
    c_ref = c._bind(x=a_ref)
    dag = d._bind({"x": b_ref, "y": c_ref})
    print(dag)

    assert ray.get(dag.execute()) == 7
    assert ray.get(ct.get.remote()) == 4


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__]))
