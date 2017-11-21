FROM openwhisk/python3action

# lapack-dev is available in community repo.
RUN echo "http://dl-4.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories

# add package build dependencies
RUN apk add --no-cache \
        g++ \
        lapack-dev \
        gfortran \
        suitesparse

# Add glibc support
RUN apk --no-cache add ca-certificates wget && \
    wget -q -O /etc/apk/keys/sgerrand.rsa.pub https://raw.githubusercontent.com/sgerrand/alpine-pkg-glibc/master/sgerrand.rsa.pub && \
    wget https://github.com/sgerrand/alpine-pkg-glibc/releases/download/2.25-r0/glibc-2.25-r0.apk && \
    apk add glibc-2.25-r0.apk

# Add base python packages
RUN pip install \
    cvxopt==1.1.8 \
    numpy \
    pandas

# Add Tensorflow
RUN pip install --upgrade \
    https://storage.googleapis.com/tensorflow/linux/cpu/tensorflow-1.4.0-cp36-cp36m-linux_x86_64.whl
