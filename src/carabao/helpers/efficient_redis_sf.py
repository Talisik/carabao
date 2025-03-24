from typing import Any, Callable, Dict, Optional, final
from typing_extensions import deprecated
from fun_things import SingletonFactory, mutate

try:
    from redis import Redis

    _exists = True

except:
    _exists = False


@deprecated("Redundant.")
class EfficientRedisSF(SingletonFactory["Redis"]):
    REDIS_WRITE_METHOD_NAMES = [
        # BasicKeyCommands
        "append",
        "bitop",
        "copy",
        "decrby",
        "delete",
        "expire",
        "expireat",
        "getdel",
        "incrby",
        "incrbyfloat",
        "lmove",
        "blmove",
        "mset",
        "msetnx",
        "move",
        "persist",
        "pexpire",
        "pexpireat",
        "psetex",
        "rename",
        "renamenx",
        "restore",
        "set",
        "setbit",
        "setex",
        "setnx",
        "setrange",
        "stralgo",
        "touch",
        # SetCommands
        "sadd",
        "sdiffstore",
        "smove",
        "spop",
        "srem",
        "sunionstore",
        # ListCommands
        "blpop",
        "brpop",
        "brpoplpush",
        "blmpop",
        "lmpop",
        "linsert",
        "lpop",
        "lpush",
        "lpushx",
        "lrange",
        "lrem",
        "lset",
        "ltrim",
        "rpop",
        "rpoplpush",
        "rpush",
        "rpushx",
        "sort",
        "sort_ro",
        # SortedSetCommands
        "zadd",
        "zdiffstore",
        "zincrby",
        "zinterstore",
        "zpopmax",
        "zpopmin",
        "bzpopmax",
        "bzpopmin",
        "zmpop",
        "bzmpop",
        "zrangestore",
        "zrem",
        "zremrangebylex",
        "zremrangebyrank",
        "zremrangebyscore",
        "zunionstore",
        # StreamCommands
        "xack",
        "xadd",
        "xautoclaim",
        "xclaim",
        "xdel",
        "xgroup_create",
        "xgroup_delconsumer",
        "xgroup_destroy",
        "xgroup_createconsumer",
        "xgroup_setid",
        # HashCommands
        "hdel",
        "hincrby",
        "hincrbyfloat",
        "hset",
        "hsetnx",
        "hmset",
    ]
    """
    List of Redis methods that involves writing.
    """

    REDIS_READ_METHOD_NAMES = [
        # BasicKeyCommands
        "bitcount",
        "bitpos",
        "dump",
        "exists",
        "expiretime",
        "get",
        "getex",
        "getbit",
        "getrange",
        "getset",
        "keys",
        "mget",
        "pexpiretime",
        "pttl",
        "hrandfield",
        "randomkey",
        "strlen",
        "substr",
        "ttl",
        "type",
        "lcs",
        # SetCommands
        "scard",
        "sdiff",
        "sinter",
        "sintercard",
        "sismember",
        "smembers",
        "smismember",
        "sunion",
        "srandmember",
        # ListCommands
        "lindex",
        "llen",
        "lpos",
        # SortedSetCommands
        "zcard",
        "zcount",
        "zdiff",
        "zinter",
        "zintercard",
        "zlexcount",
        "zrandmember",
        "zrange",
        "zrevrange",
        "zrangebylex",
        "zrevrangebylex",
        "zrangebyscore",
        "zrevrangebyscore",
        "zrank",
        "zrevrank",
        "zscore",
        "zunion",
        "zmscore",
        # StreamCommands
        "xinfo_consumers",
        "xinfo_groups",
        "xinfo_stream",
        "xlen",
        "xpending",
        "xpending_range",
        "xrange",
        "xread",
        "xreadgroup",
        "xrevrange",
        "xtrim",
        # HashCommands
        "hexists",
        "hget",
        "hgetall",
        "hkeys",
        "hlen",
        "hmget",
        "hvals",
        "hstrlen",
    ]
    """
    List of Redis methods that does not involve writing.
    """

    __read_only_kwargs_fn: Optional[Callable[[], Dict[str, Any]]] = None
    __read_only_redis: Optional["Redis"] = None

    def _instantiate(self):
        if not _exists:
            raise ImportError("You don't have `redis` installed!")

        redis = Redis(
            *self.args,
            **self.kwargs,
        )

        if not self.__read_only_kwargs_fn:
            return redis

        read_only_kwargs = self.__read_only_kwargs_fn()

        if not read_only_kwargs.get("host"):
            return redis

        self.__read_only_redis = Redis(
            **read_only_kwargs,
        )

        mutate(
            redis,
            self.REDIS_READ_METHOD_NAMES,
        ).replace(self.__read_only_redis)

        return redis

    def _destroy(self):
        self.instance.close()

        if self.__read_only_redis:
            self.__read_only_redis.close()

        return True

    @final
    @classmethod
    def new(
        cls,
        fn: Callable[[], Dict[str, Any]],
        read_only_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        singleton = super().new(fn)

        if read_only_fn:
            singleton.__read_only_kwargs_fn = read_only_fn

        return singleton
