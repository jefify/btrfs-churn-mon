BEGIN {
    FS="[ \t]+"
}

/^write[ \t]/ {

    path=$2

    sub(/^\.\//,"",path)

    if (match($0,/len=[0-9]+/)) {

        bytes = substr($0,RSTART+4,RLENGTH-4) + 0

        churn[path] += bytes
    }

    next
}

/^clone[ \t]/ {

    path=$2

    sub(/^\.\//,"",path)

    if (match($0,/len=[0-9]+/)) {

        bytes = substr($0,RSTART+4,RLENGTH-4) + 0

        churn[path] += bytes
    }

    next
}

END {

    for (k in churn)
        printf "%d\t%s\n", churn[k], k
}
