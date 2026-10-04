---
title: Making my concurrent algorithm 6,000% better
date: '2023-10-29T20:11:11Z'
draft: false
original_url: https://dev.to/charlietap/making-my-concurrent-algorithm-6000-better-24oo
lastmod: '2023-10-30T11:25:53Z'
---
Would you trade a little bit of memory for a whole lot of concurrency?

This is the concept behind a concurrent data structure I've been implementing in my [Kotlin Multiplatform library](https://github.com/CharlieTap/cachemap).

The data structure is known as LeftRight and it's here to give you an alternative to those pesky locks that everyone wraps around shared mutable state.

I'll explain


## What is LeftRight?

![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/15woh53eniulrbungjgp.png)


LeftRight is a concurrency primitive, it allows you to turn any mutable data structure into a concurrent version of itself.

For example... Have a mutable set you need to be thread safe?

Voilà

```kotlin
val sharedSet = LeftRight<MutableSet<T>>(::mutableSetOf)
```

Or more likely you have mutable HashMap ... 

```kotlin
val sharedMap = LeftRight<MutableMap<K, V>>(::mutableMapOf)
```

Or any other data structure you may want to share, LeftRight is generic over T and just requires a constructor for T to work. 

> _That's cool but why would I bring in your library as another dependency to my project when I can just wrap my data in a lock?_

Well you'd be saying goodbye to all of your concurrent performance if you did that. Locks don't scale. LeftRight doesn't use locks, at least not for coordinating reads and writes.



> _How can your library be safely exposing state whilst allowing reads and writes to access the same memory address, that's impossible?_


You're right that's impossible...

> _What???_

Maybe the picture above can give you a clue... 

Nope? Okay...

## How do we LeftRight?

At its core LeftRight is incredibly simple, it consists of two copies of a given data structure and an atomic pointer. The atomic pointer works like a traffic warden at a fork in the road, directing read traffic to one data structure and write traffic to the other.

> _So we have 2x the memory footprint?_

Probably not no, Kotlin is a pointer heavy language, data structures tend to store references to objects rather than the objects themselves. So what we end up with is just two times the amount of pointers.

The beauty of LeftRight lies in its ability to allow reads to progress without using locks or even asking them to wait. And this isn't an easy feat!

**The problem**

Imagine we have a `LeftRight<MutableSet>`, this means we will have two MutableSets internally, we'll call them L and R for short. Initially the atomic pointer is directing writes to L and reads to R.

A write comes in and we update L.

Now we somehow need to let readers know about the change, so we redirect the pointer such that L is now accepting reads and R is now accepting writes.

But we haven't applied the change from before to R yet, so no problem right we just apply it to R and we're good?

Nope, this isn't safe, because we don't know if readers have departed from R yet. Maybe they read the pointer just before we redirected it and are now about to read from the side we also are about to write to ... Somehow we need to signal to writes that reads have departed without using traditional lock/wait based solutions like mutexes or semaphores.

LeftRight has a very clever solution to this problem, the algorithm goes something like this:

We create a global array of counters (these are just 32 bit Ints)

```kotlin
val counters: Array<Counter> = arrayOf(maxReaderParallelism)
```

When a read comes in:

1. We increment our counter
2. We read from the data structure designated by the atomic pointer
3. We increment our counter again

Given each reader thread has its own index into the global array and thus its own private counter, we can infer that there is only ever one thread writing to the counter. If there is only one writer then we do not need any locks or waits. In fact the counters needn't even be atomic as a CAS loop would never fail, we do however need to mark them as volatile to ensure all threads see the events in the order they happened and that the compiler doesn't rearrange our code in weird and wonderful ways.

For writes:

1. We perform the write on the data structure designated by the atomic pointer
2. We switch the atomic pointer so now reads will see this update
3. Now we need to wait for readers to depart from the old read side (the new write side)
4. We perform the write again on the new write side of the data structure

So how do we determine that readers have departed?

This is where the counters come in and the magic happens. Remember reads increment the counter twice, once before and once after a read. When the counter is odd, we know a reader is actively in the map, but when it's even we know it's finished its work and the following read will have to go through the atomic pointer again. So, we filter out all the counters that are odd and then we loop on them, waiting for them to change, not necessarily become even, but change. Any change means that the counter will have moved onto the new write side of the data structure.

What's with the weird sizing on the counter array?

The size of this array dictates the amount of reader threads left right supports, this is one of the constraints on my implementation. If we allowed the array to grow or be resized then we would have to wrap it in a lock. Instead we attempt to anticipate the upper bound on threads in your program, we do this using the same logic Kotlin coroutines does for thread pool sizing.


## Why LR?

![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/93thytet1g9iqp7pyxf4.png)

I created LR for two reasons:

- There are no Kotlin Multiplatform concurrent datastructures
- Locks are not a suitable replacement in 2023

Kotlin Multiplatform is still in its infancy, at present there are no Kotlin Multiplatform concurrent data structures. You can't simply reach for ConcurrentHashMap like you could when you were working within the JVM ecosystem, everything depends on what targets your project supports. 

In the absence of the wealth of JVM based libraries, I see more and more people reaching for locks. Whilst this may be perfectly acceptable for a given use case, I don't believe generally replacing concurrent data structures with locks is a smart move in 2023.

Locks strip our multicore CPUs of their parallelism super powers through contention, and contention isn't something that's going to go away, quite the opposite actually it's going to augment. Computers are gaining more cores year on year, high end consumer chips now have up to 24 cores, that will shortly rise to 32 and within the next decade we will undoubtedly see core counts that breach the 100 mark. Do you really want 99 cores waiting on your mutex? We'll see the performance ramifications of this later on.

LeftRight gives you a scalable alternative to locks and positions itself as a generic concurrent data structure with more than acceptable performance. 

LeftRight is not a direct competitor to the highest performing concurrent data structures, like ConcurrentHashMap for example. ConcurrentHashMap is a bespoke concurrent HashMap implementation, it's not a wrapper around a HashMap, it **is** the HashMap. LeftRight however is a generic wrapper around a data structure, as always with indirection we incur the cost of chasing pointers. LeftRight is also entirely ignorant to the workings of the thing it wraps, it knows just two invariants, that reads will occur and that writes will occur. For this reason it's unable to provide domain specific optimisations. 


## Less talk more benchmarks


![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/799hgnk0jud3blp00kma.png)


Time to put my money where my mouth is, I've been moaning a fair bit about locks, let's dive into some benchmarks.

We're going to compare:

- Java's ConcurrentHashMap (The gold standard 👑)
- LeftRight (The new kid 🤠)
- ReentrantReadWriteLock (The best locks have to offer 🔒)

I've been generous here, rather than use a standard mutex I've gone with a read write mutex in order to really get the best out of locks.

The below benchmarks are all run on an Apple M1 Max, the benchmark suite can be found in the repo [here](https://github.com/CharlieTap/cachemap/tree/main/benchmark)


### ReentrantReadWriteLock 

| Operation         | Single Threaded     | Multi Threaded      |
|-------------------|---------------------|---------------------|
| read throughput   | 0.0069 ops/ns       | 0.0018 ops/ns       |
| read avg time     | 14 ns/op            | 5,783 ns/op         |
| write throughput  | 0.0789 ops/ns       | 0.0056 ops/ns       |
| write avg time    | 13 ns/op            | 227 ns/op           |


Single threaded benchmarks look pretty good as you would expect of a lock under no contention but it's not looking so great for the multithreaded side of things. The average time of a read is 400x slower and overall throughput around 6x less when accessing the hashmap from multiple threads.  

### LeftRight

| Operation         | Single Threaded     | Multi Threaded      |
|-------------------|---------------------|---------------------|
| read throughput   | 0.0808 ops/ns       | 0.6449 ops/ns       |
| read avg time     | 12 ns/op            | 16 ns/op            |
| write throughput  | 0.0381 ops/ns       | 0.0324 ops/ns       |
| write avg time    | 28 ns/op            | 437 ns/op           |


LeftRight shows a remarkable improvement in both single threaded and multi threaded benchmarks. More importantly the multithreaded throughput of reads is showing an 8x linear improvement which checks out given my CPU has 8 performance cores. Writes are as expected given they are serialised with a mutex.

### ConcurrentHashMap

| Operation | Single Threaded | Multi Threaded           |
|----------------------------|--------------------------|--------------------------|
| read throughput    | 0.1406                   | 1                        |
| read avg time   | 7 ns/op                 | 9 ns/op                  |
| write throughput    | 0.0093                   | 0.0073                   |
| write avg time   | 10 ns/op                | 1,398 ns/op              |

As expected reads are blazingly fast and ahead of both the previous two implementations, but interestingly LR comes within 80-90% which is better than we could have hoped for a data structure with inherently more indirection. Writes seem to struggle but this is likely a quirk of the benchmark writing to the same key and thus the same bin (ConcurrentHashMap uses bin level locking), in reality writes would have a much fairer distribution and I would expect Concurrent HashMap to come out on top.

Here's a graph depicting all the above courtesy of ChatGPT 


![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/vg0wx2ztwi1c68hop32s.png)


## What you came here for 

LeftRight is remarkably performant for a generic concurrency primitive. But things weren't always this way... let's take a look at an earlier implementation's benchmark

| Operation          | Single Threaded | Multi Threaded |
|--------------------|-----------------|----------------|
| read throughput    | 0.0716 ops/ns   | 0.0107 ops/ns  |
| read avg time      | 14 ns/op        | 534 ns/op     |
| write throughput   | 0.0368 ops/ns   | 0.0376 ops/ns  |
| write avg time     | 27 ns/op        | 442 ns/op     |

You can see from the above, the performance takes a nose dive with the introduction of more threads/cpu cores. I expected this to be the case for mutations, after all we have a single writer policy which is enforced using a lock.

But for reads this didn't make sense at all, not only is the average time of a read 50x slower but the throughput is 7x less??? I'm using a lock-free/wait-free algorithm for reads! Wtf??? There's no shared memory and nothing for threads to contend on???

Well ...

![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/35a59jj6lrffxeovkydj.png)

It transpires that it's not enough to have threads guard their own private memory when accessing shared resources. Due to the nature of modern CPU cache architectures, even adjacent memory locations can be a source of contention.

It's like contention through osmosis 😭 😭

This phenomenon, known as false sharing, occurs when multiple threads, running on different cores, access different variables that reside on the same cache line. Even though they're not directly sharing data, the mere fact that their data resides closely in memory means they effectively compete for the same cache line. This can cause performance degradation as threads constantly invalidate each other's cache lines, even if they're not accessing shared data directly.

Honestly I just keep coming back to this quote over and over again in my career...

> There are only two hard things in Computer Science: cache invalidation and naming things.
> -- Phil Karlton

So how do we fix this?

The problem stems from the original implementation of my global counter array

```kotlin
val globalEpochArray = Array<AtomicInt>(64)
```

When the array's allocated, it will more than likely allocate those 64 AtomicInt objects next to one another on the heap.

AtomicInt is just a wrapper around a 4 byte integer, and every class has a 12 byte (on a 64 bit JVM) object header, making one allocation of AtomicInt take 16 bytes of space.

So we now have a 16 * 64 byte block of contiguous memory allocated on the heap.

When thread 1 loads the first counter (which should be just [0 - 16] bytes) it in fact loads an entire cache line worth of memory, on my laptop (M1 Max) an L1 cache line is 128 bytes. So now the core running thread one has the first [0 - 128] bytes and thus the first 8 counters inside of its cache line. 

When thread 2 tries to load the second counter it does the same, now thread 2 has counters 2 through to 10 in its cache line.

Now what happens when thread 1 mutates its counter? 

It invalidates the cache line of up to 8 other cores, and when poor thread two comes round to trying to change its counter, it now has to load it from RAM again.

To give a rough idea of impact here's the load times between L1 CPU cache and RAM:

L1 Cache Lookup: 0.5 to 1 nanoseconds.
RAM Lookup: 50 to 100 nanoseconds

This explains my average read time went from 14ns to 534ns

So how do we stop this? 

With this abomination

```kotlin
class PaddedVolatileInt(initialValue: Int) {

    @Volatile private var p1: Long = 0
    @Volatile private var p2: Long = 0
    @Volatile private var p3: Long = 0
    @Volatile private var p4: Long = 0
    @Volatile private var p5: Long = 0
    @Volatile private var p6: Long = 0
    @Volatile private var p7: Long = 0
    @Volatile private var p8: Long = 0
    @Volatile private var p9: Long = 0
    @Volatile private var p10: Long = 0
    @Volatile private var p11: Long = 0
    @Volatile private var p12: Long = 0
    @Volatile private var p13: Long = 0
    @Volatile private var p14: Long = 0

    @Volatile var value: Int = initialValue
}
```
Essentially we pad our counter object such that it fits perfectly inside an L1 cache line.

12 byte header + (14 * 8) + 4 = 128 bytes

This really isn't an ideal solution, padding should be dynamic such that CPUs with smaller cache lines are accommodated for but well we don't have this level of control from Kotlin.

But with that change our multithreaded throughput rises and average time falls dramatically.

| Operation        | Before (Multi Threaded) | After (Multi Threaded) | % Change           |
|------------------|-------------------------|------------------------|--------------------|
| read throughput  | 0.0107 ops/ns           | 0.6449 ops/ns          | +5927.10%          |
| read avg time    | 534 ns/op               | 16 ns/op               | -97.00%            |
| write throughput | 0.0376 ops/ns           | 0.0324 ops/ns          | -13.83%            |
| write avg time   | 442 ns/op               | 437 ns/op              | -1.13%             |

The value of throughput now grows linearly with the amount of cores available, thus you would see different increases/decreases depending on the machine.

## Rapping up


![Image description](/uploads/imports/making-my-concurrent-algorithm-6000-better/b3j9dacrlp8bar2ama4q.png)

You can find my repository containing LeftRight [here](https://github.com/CharlieTap/cachemap), you'll notice that the repo is actually called cachemap. That's because the repo contains two libraries, LeftRight and CacheMap, the latter is essentially just a batteries included `LeftRight<MutableMap>`. 

Both LeftRight and CacheMap are experimental at the moment so please proceed with caution despite the positive looking benchmarks. Be extra careful with the suspending variants as these haven't yet been benchmarked nor optimised. 

There are lots of optimisations to be made, writes suck more than they need to at the moment. I have a rough design of a write batching algorithm which should amortise the cost of the lengthy writer wait step.

I'm currently in the process of publishing the artifacts in Maven Central (the process is not fun 🤯), hopefully by the time you read this I will have instructions on the repo of how to pull each artifact.


### Acknowledgements 

I learned of LeftRight in a [youtube stream from Jon Gjengset](https://www.youtube.com/watch?v=eLNAMEoKAAc) a while back, Jon is in my opinion the best comp sci content creator out there. 

You can also find what I believe to be the first paper on the primitive [here](https://hal.science/hal-01207881/document).

All Illustrations were created by the incredible artist that is Dalle 3
