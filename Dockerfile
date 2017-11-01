FROM openwhisk/python3action

# lapack-dev is available in community repo.
RUN echo "http://dl-4.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories

# add package build dependencies
RUN apk add --no-cache \
        g++ \
        lapack-dev \
        gfortran \
        suitesparse

# Add base python packages
RUN pip install \
    numpy \
    pandas

# Add CVXOpt
RUN pip install \
    cvxopt==1.1.8
