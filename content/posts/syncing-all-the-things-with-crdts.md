---
title: Syncing all the things with CRDTs
date: '2023-04-12T09:39:20Z'
draft: false
original_url: https://dev.to/charlietap/synking-all-the-things-with-crdts-local-first-development-3241
lastmod: '2023-04-12T09:53:26Z'
---
So you want to build a local first application? You want the application to work both offline and online seamlessly with no interruption to the end user? 

How hard could it be right?...

![A Dalle-2 generated image of a monkey trying to solve an impossible puzzle](/uploads/imports/syncing-all-the-things-with-crdts/7iuedxigj9zfaeudhekf.png)

For the past few months I've been working on a library in this space, something quite novel that I think offers an avenue for simplifying local first development and the challenges it presents. But before I introduce Synk I think it's worth exploring this problem space, taking a look at why it's particularly tricky and what existing solutions are out there. This blog post should serve as a good primer for anyone looking to get into local first development and CRDTs.

Local first applications work offline, they work in isolation, the application shouldn't need to be connected to the internet in order to function. From a technical perspective this is a grand departure from traditional client server applications. 

In order to work detached from the network, the client device must be capable of computing all the states that would typically be derived by the server... that's a lot of business logic on the client. So the client's FAT, so what? Well that aside you've just decided to create a distributed system and with that comes an entire field of computer science worth of problems!

But wait how did this happen?

Let me explain, in a traditional client server architecture, the server is gospel, the state it holds is the truth and entirety. We'll skip over the fact that most servers are a facade hiding a deeper distributed system, the net of distribution we cast extends only as far as the server infrastructure, not the clients themselves. Whereas in a distributed system, the totality of the state is not found in a single node (like the server) the state is the aggregation of the state found across all the nodes in the system. Now that the client application can work and evolve in isolation from the network (and importantly the centralised server state), we've undoubtedly waded into distributed waters.

>**_That's Cap! ...Theorem_**

Okay so we're saying that local first applications are actually complex distributed systems, we should probably classify what type. If you ever had the pleasure of sitting through a CS lecture on DS then you've probably come across CAP Theorem. In a nutshell it states that distributed systems can have at most two of the three following properties:

| Property | Description |
| --- | ----------- |
| Consistency | Every read receives the most recent write or an error. |
| Availability | Every request receives a (non-error) response, without the guarantee that it contains the most recent write. |
| Partition tolerance | The system continues to operate despite an arbitrary number of messages being dropped (or delayed) by the network between nodes |

![Image description](/uploads/imports/syncing-all-the-things-with-crdts/i0bbk7llo2frx5ac40bv.png)

Having at most two of the above properties means we end up with systems that are either CA, CP or AP. Can you guess what property doesn't hold in local first applications? ...

It's Consistency, we're unable to guarantee strong consistency because we want them to work offline, they can't possibly return the most recent write if they can't coordinate with other nodes in the system. Instead they are what we call "_Eventually Consistent_", once they have reconnected and synchronised the latest changes. In my opinion dropping the C is a blessing, solutions that guarantee strong consistency involve complex consensus algorithms... If you've ever studied Paxos or Raft you'll know why I say this is a good thing. 

Okay so we're AP, Local first applications are AP distributed systems, cool, well what does that mean? Well it means we'll face a certain subset of problems and we can lean on a subset of solutions. Let's have a look at the type of problems we will face.

| Problem | Description |
| --- | ----------- |
| Replication | How do changes get propagated to other clients without being lost? |
| Conflict resolution | What happens when two devices change the same piece of data whilst offline? Whose change wins and why? |
| Causal Ordering | Who changed what when exactly? Can you really be sure on a timeline of events? What if the local clocks on the clients are out of synk?.. oops I mean sync |


Spoiler! Synk concerns itself with the bottom two. After all it's quite likely you already have made up your mind on how you want to propagate data, for example what transport (Http, RPC, Sockets) and serialization format you want to use in your application. So replication is on you... but we have solutions for the rest. It's about time I introduce one of the most common solutions in AP distributed systems and exactly the thing you'll need to replicate.

## CRDTs

> **_"It's Cee Arr Dee Tees not Serdts"_**

CRDTs also known as Conflict-free replicated data types are the mechanism we will use to achieve "Eventual Consistency" in our AP distributed system.

In simple terms, they're data structures that cannot conflict, each (and there are many!) has an algorithm that lets them deterministically merge updates. For almost all basic data structures you can think of (maps, sets, lists etc) there will exist CRDT implementations, often with different quirks but all guaranteeing conflict free merging of updates.

Now if we're to use proper Distributed systems terminology these updates which are sent between nodes to keep the system up to date are known as "Messages". CRDTs are categorised by what's contained in the messages they produce. 

| Category | Behaviour |
| --- | ----------- |
| State | State based CRDTs will send messages that include the entire current state of the CRDT. This can be thought of as being similar to a POST/PUT request |
| Operation | Operation based CRDTs will send messages that include the operation and parameters that need to be applied. This can be thought of as being similar to an RPC call. |
| Delta | Delta based CRDTs will send messages that contain only the values that have changed in the CRDT. This can be thought of as being similar to a PATCH request |

And that's not all, CRDTs are **ACID 2.0**. Another acronym if you hadn't guessed, let me break that down for you:


- **Associative**

```mathematica
(a + b) + c = a + (b + c)
```

This means it doesn't matter how you group the merges

- **Commutative**

```mathematica
a + b = b + a
```

This means it doesn't matter if you merge a into b or b into a, it's the same

- **Idempotent**

```mathematica
a + a + a + b = a + b
```

This means you can merge the same CRDT multiple times but the result doesn't change

- **Distributed**

```mathematica
???
```

In all honesty this is here to make the acronym work 🤣

The above properties are incredibly powerful and make the job of replication in AP systems far far simpler. It doesn't matter if you accidentally send the same CRDT twice, it doesn't matter if you send updates out of order, it doesn't matter if you merge client A's updates into client B's before merging client C's... The system will always reach the same deterministic result (That's the whole eventually consistent thing I mentioned).

Now you might be thinking, that's a lot of rules surely it's hard to create something that satisfies all those constraints. But honestly it's simpler than you might think, I'm going to run you through the two Synk uses under the hood and you'll see what I mean.

Alright first up my favourite, and arguably the simplest...

> **_Ladies and gentlemen please welcome G-SET!!!_**

![A Dalle-2 generated image of Ali G replicating himself](/uploads/imports/syncing-all-the-things-with-crdts/1eb6exwylkz0zzluobjy.png)

A G-Set or Grow-only Set is simply a Set without the remove operation, meaning it grows and never shrinks. Let's have a look at its behaviour in pseudocode: 

```kotlin
val gset = GSet<String>()
gset.add("foo") 

// println(gset) 
// [
//  “foo”,
// ]

gset.add("foo")
gset.add("bim")
gset.add("bar")

// println(gset) 
// [
//   “bar”,
//   “bim”,
//   “foo”,
// ]

```

A G-Set merges by set union, which is associative and commutative: neither the order nor the grouping of merges changes the result. It's idempotent because being a set it disallows duplicates. A G-Set is ACID 2.0 compliant making it a verified CRDT... 

The elephant in the room at this point is that it doesn't seem particularly useful. But like all data structures in computer science CRDTs can and should be composed together to model larger structures. A G-set is a collection, so now we need the collection to hold something useful, another CRDT. 

Without further Ado I introduce LWW-Map

It stands for "Last write wins map" and it's a key value map with a couple of stipulations. 

1. The value has to be a tuple where one of the items is always a timestamp. On map insertion if the key already exists then the existing timestamp is compared with the new timestamp and the victor is the most recent.

2. You can't delete entries, that's generally a recurring theme in CRDTs but we'll address that shortly. 

You can get an idea of its behaviour from the following pseudocode:

```kotlin
val map = LWWMap()
map["foo"] = Pair("Ali G", 123)

// println(map) 
// {
//  “foo” : { “value”: “Ali G”, “ts”:123 },
// }

map["foo"] = Pair("Ali G is da best", 234)
map["foo"] = Pair("Ali G is da best", 234)
map["foo"] = Pair("Ali G is not da best", 112)

// println(map) 
// {
//   “foo” : { “value”: “Ali G is da best”, “ts”:234}
// }

```

Maps ultimately allow us to serialize structs/data classes, so now combining both a G-Set and an LWW Map we can model collections of classes.

James Long took this observation further in his talk [CRDTs for mortals](https://www.youtube.com/watch?v=DEcwa68f-jY), and stated that we can actually make tables in databases behave like G-Sets of LWW-Maps with a few tweaks. Stay with me here I appreciate this is a leap of faith but we'll run through it.

Tables with primary keys can behave like G-Sets so long as we never remove entries, a table is a collection of rows after all. But what about modelling a row as an LWW Map? Let's take a look at an example

| id | fn | ln | age |
| -- | -- | -- | --- |
| 1 | bob | smith | 35 |
| 2 | jack | jones | 28 |

The rows in the table above couldn't possibly satisfy the conditions of an LWW-Map because they're missing the associated timestamp data. So let's add that

| id | fn | fn_ts | ln | ln_ts | age | age_ts |
| -- | -- | ----- | -- | ----- | --- | ------ |
| 1 | bob | 12345 | smith | 12345 | 35 | 12345 |
| 2 | jack | 12345 |jones | 12345 | 28 | 12345 |

Notice the id in the table above is the only column without timestamp meta, this is because it functions as the key in the map and is immutable, immutable values cannot change and thus the meta isn't needed. For the rest, if we check the current timestamp on insertion and use this to determine the new value and timestamp then our row behaves as an LWW Map, turning our table into a CRDT.

But I need to delete things? 😅

I thought you'd say that, well I have a solution, it's imperfect but it works.  

### Tombstones

Tombstones are also known as soft delete flags outside the realms of distributed systems. It's a reasonably simple concept, add a flag to signify whether a record has been deleted, use this same flag to ignore deleted records in subsequent queries.

| id | fn | fn_ts | ln | ln_ts | age | age_ts | del | del_ts |
| -- | -- | ----- | -- | ----- | --- | ------ | --- | ----- |
| 1 | bob | 12345 | smith | 12345 | 35 | 12345 | 0 | 12345 |
| 2 | jack | 12345 |jones | 12345 | 28 | 12345 | 1 | 12345 |


> **_I've got 99 problems but a conflict ain't one_**

CRDTs are an awesome solution to a difficult problem, personally I find them to be the most natural solution in the  distributed systems domain, but I must admit I have problems with existing libraries that leverage them. 

CRDTs are usually implemented in two ways, either at the domain level, which requires objects to implement some mergeable interface, or at the data level, in the form of a very bespoke (often not general purpose) datastore. The common denominator is an intrusive piece of technology which has a large impact on the shape and design of the application you are creating.

What if this wasn't the case? What if we could have conflict resolution as a pluggable piece of software? Something we could bootstrap existing systems with to give them distributed powers.



## Synk


> _A Kotlin Multiplatform CRDT library for local first applications_.

Synk is a state based CRDT library, it monitors state changes over time using a special type of [timestamp](https://github.com/charlieTap/hlc) which is capable of tracking events in a distributed system. Synk maintains this data in its own persistent key value storage database locally on each client, 

It's important to understand Synk does not store your data, merely it stores timestamps associated with it. Remember that timestamp data we added to the table? Well Synk tracks that separately, leaving your data layer entirely untouched, allowing you to build apps with the same technologies you always have.

At its core Synk is comprised of just two functions!

```kotlin
Synk.outbound(new: T, old: T? = null): Message<T>
```
_Whenever a new record/object is created or updated in your application locally, give Synk the latest version and the old version (if applicable) and Synk will return you a message. This message needs to be propagated to all other clients._

```kotlin
Synk.inbound(message: Message<T>, old: T? = null): T 
```

_When receiving a Message from another client application, inbound needs to be called. This function will perform conflict resolution for you and return an instance of your object ready to be persisted._

Synk is deliberately minimal, you give it objects and it gives you messages, propagate those messages to the right clients and your application will have no conflicts, it's that easy!

> **_A distributed database... but you bring the database_**

I'm excited to see what people come up with using this technology, the innovation in the CRDT space right now is crazy. Ultimately I had an idea with this project of creating a minimal library which gives the tools to turn a local database into a distributed one, all whilst exposing some but not all of the distributed primitives. The result is something quite novel, I hope the idea of using CRDTs to resolve your conflicts has piqued your interest.

There's a bunch of detail I chose to omit in this blog, more for brevity than anything else. However there's a lot more information on the repository if you're interested! I've learned so much building out this project, I hope this blog has taught you a thing or two yourself.


### References

1. A huge inspiration in all the above was James Long's presentation [CRDTs for mortals](https://www.youtube.com/watch?v=DEcwa68f-jY), if you haven't seen it already go and watch, it's awesome


_**All images were generated by Dalle-2, you can see the prompts I used below**_


| Image | Prompt |
| --- | ----------- |
| ![Original illustration](/uploads/imports/syncing-all-the-things-with-crdts/ityoe5jt3av5tsl8rdf7.png) | “An oil painting of 4 databases trying really hard to synchronise with each other” |
| ![Original illustration](/uploads/imports/syncing-all-the-things-with-crdts/7iuedxigj9zfaeudhekf.png) | “An oil painting of a monkey attempting to solve the most complex puzzle imaginable” |
| ![Original illustration](/uploads/imports/syncing-all-the-things-with-crdts/1eb6exwylkz0zzluobjy.png) | “Ali G replicating himself into multiple people as an oil painting” |

